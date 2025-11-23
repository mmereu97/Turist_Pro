import sys
import os
from dotenv import load_dotenv
import traceback
import googlemaps
import requests
import json
import webbrowser
import math

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculează distanța în metri între două coordonate GPS."""
    try:
        R = 6371000  # Raza Pământului în metri
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        
        a = math.sin(dphi / 2)**2 + \
            math.cos(phi1) * math.cos(phi2) * \
            math.sin(dlambda / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    except:
        return 0.0

from PySide6.QtWidgets import (QTabBar, 
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QCheckBox, QTextEdit,
    QFrame, QScrollArea, QComboBox, QTabWidget, QListWidget, QDialog,
    QMessageBox, QButtonGroup, QSizePolicy, QGroupBox, QDialogButtonBox,
    QAbstractItemView, QListWidgetItem, QMenu, QFileDialog
)
from PySide6.QtCore import Qt, QByteArray, Signal, QTimer, QMimeData, QUrl, Slot, QObject, QFileInfo, QSize
from PySide6.QtGui import QPixmap, QFont, QCursor, QImage, QDrag, QAction, QGuiApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from PySide6.QtWebChannel import QWebChannel






class WebPage(QWebEnginePage):
    """Pagină web custom care afișează erorile de JS în consola Python."""
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        # Filtrare mesaje irelevante pentru utilizator
        if "[CULOARE]" in message: return
        if "google.maps.Marker is deprecated" in message: return
        
        log_info(f"JS CONSOLE: {message} (Linia {lineNumber})")


# --- Clase și constante (modificate) ---
class Colors:
    OKGREEN = '\033[92m'
    FAIL = '\033[91m'
    WARNING = '\033[93m'
    OKBLUE = '\033[94m'
    HEADER = '\033[95m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'

def log_debug(message, color=Colors.OKBLUE):
    print(f"{color}[DEBUG] {message}{Colors.ENDC}")

def log_success(message):
    print(f"{Colors.OKGREEN}{Colors.BOLD}[SUCCESS] {message}{Colors.ENDC}")

def log_error(message):
    print(f"{Colors.FAIL}{Colors.BOLD}[ERROR] {message}{Colors.ENDC}")

def log_warning(message):
    print(f"{Colors.WARNING}[WARNING] {message}{Colors.ENDC}")

def log_info(message):
    print(f"{Colors.HEADER}[INFO] {message}{Colors.ENDC}")

STATE_FILE = "app_state.json"

# NOU: Setări implicite pentru Gemini AI
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash-lite"
DEFAULT_AI_PROMPT = """Ești un analist expert în recenzii. Analizează următoarele recenzii și oferă:

1. **Rezumat general** - Ce spun clienții în general despre acest loc
2. **Puncte forte** - Ce apreciază cel mai mult clienții (3-5 puncte)
3. **Puncte slabe** - Ce critici sau nemulțumiri apar frecvent (3-5 puncte)
4. **Recomandare** - Pentru cine este potrivit acest loc și pentru cine nu

Fii concis, obiectiv și bazează-te doar pe informațiile din recenzii. Răspunde în limba română."""

log_info("Aplicația pornește (Mod: Distance Matrix + AI Summary)...")
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)
api_key = os.getenv("GOOGLE_API_KEY")

try:
    gmaps_client = googlemaps.Client(key=api_key)
    log_success("Clientul Google Maps a fost inițializat cu succes.")
except Exception as e:
    log_error(f"Inițializarea clientului Google Maps a eșuat: {e}")
    sys.exit()

# Variabile pentru starea curentă a hărții
current_map_lat = None
current_map_lng = None
current_map_name = None
current_zoom_level = 15
current_map_place_id = None
current_search_results = []
current_distance_info = {}
saved_locations = {}
my_coords_full_address = ""
explore_coords_full_address = ""
selected_places = {}

# NOU: Dict pentru a stoca coordonatele locațiilor din traseu
route_places_coords = {}

# NOU: Dict pentru a păstra culorile inițiale ale locațiilor (nu se schimbă la mutare)
place_initial_colors = {}

# Variabile globale pentru setări AI
gemini_model_value = DEFAULT_GEMINI_MODEL
ai_prompt_var = DEFAULT_AI_PROMPT

# --- Configurare Categorii Diversitate (Granularitate Maximă) ---
CATEGORIES_MAP = {
    # --- MÂNCARE & BĂUTURĂ ---
    'restaurant': {
        'label': '🍴 Restaurante',
        'keywords': ['restaurant', 'meal_takeaway', 'meal_delivery']
    },
    'cafe': {
        'label': '☕ Cafenele/Patiserii',
        'keywords': ['cafe', 'bakery', 'coffee_shop']
    },
    'bar': {
        'label': '🍻 Bar/Club/Viață de noapte',
        'keywords': ['bar', 'night_club', 'casino', 'liquor_store']
    },
    
    # --- CULTURĂ & TURISM ---
    'museum': {
        'label': '🏛️ Muzee & Artă',
        'keywords': ['museum', 'art_gallery']
    },
    'religion': {
        'label': '⛪ Religie/Spiritual',
        'keywords': ['church', 'place_of_worship', 'synagogue', 'mosque', 'hindu_temple']
    },
    'tourist': {
        'label': '📸 Atracții Turistice',
        'keywords': ['tourist_attraction', 'city_hall', 'stadium', 'landmark']
    },
    
    # --- NATURĂ & DISTRACȚIE ---
    'park': {
        'label': '🌳 Parcuri & Natură',
        'keywords': ['park', 'natural_feature', 'campground', 'rv_park']
    },
    'fun': {
        'label': '🎡 Zoo/Distracție/Film',
        'keywords': ['amusement_park', 'zoo', 'aquarium', 'bowling_alley', 'movie_theater']
    },
    
    # --- SHOPPING ---
    'mall': {
        'label': '🛍️ Mall/Fashion',
        'keywords': ['shopping_mall', 'clothing_store', 'department_store', 'jewelry_store', 'shoe_store', 'electronics_store']
    },
    'market': {
        'label': '🛒 Supermarket/Băcănie',
        'keywords': ['supermarket', 'grocery_or_supermarket', 'convenience_store']
    },
    'books': {
        'label': '📖 Librării/Biblioteci',
        'keywords': ['book_store', 'library']
    },
    
    # --- UTILITĂȚI & URGENȚE ---
    'pharmacy': {
        'label': '💊 Farmacii/Sănătate',
        'keywords': ['pharmacy', 'drugstore', 'hospital', 'doctor']
    },
    'bank': {
        'label': '🏧 Bănci/ATM',
        'keywords': ['bank', 'atm']
    },
    'fuel': {
        'label': '⛽ Benzinării',
        'keywords': ['gas_station']
    },
    'transport': {
        'label': '🚆 Transport (Gară/Bus)',
        'keywords': ['train_station', 'bus_station', 'subway_station', 'transit_station', 'airport']
    }
}

# Setări implicite extinse (Min/Max)
# min = Garanție (Dacă nu sunt destule, caută activ)
# max = Plafon (Dacă sunt prea multe populare, ignoră restul)
diversity_settings = {
    'restaurant': {'min': 2, 'max': 5, 'min_rating': 4},
    'cafe':       {'min': 2, 'max': 4, 'min_rating': 4},
    'bar':        {'min': 0, 'max': 3, 'min_rating': 4},
    'museum':     {'min': 2, 'max': 5, 'min_rating': 4},
    'religion':   {'min': 3, 'max': 5, 'min_rating': 0}, # Prioritate Biserici
    'park':       {'min': 2, 'max': 4, 'min_rating': 4},
    'mall':       {'min': 1, 'max': 2, 'min_rating': 4},
    'pharmacy':   {'min': 1, 'max': 2, 'min_rating': 0}, 
    'bank':       {'min': 0, 'max': 2, 'min_rating': 0},
    'market':     {'min': 0, 'max': 2, 'min_rating': 0}
}


def parse_coordinates(coords_string: str):
    try:
        parts = coords_string.split(',')
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
        return lat, lon
    except Exception:
        return None


def reverse_geocode(lat, lng):
    """Obține adresa pentru coordonatele date folosind Google Geocoding API."""
    try:
        log_info(f"Reverse geocoding pentru {lat}, {lng}...")
        result = gmaps_client.reverse_geocode((lat, lng), language='ro')
        
        if result and len(result) > 0:
            log_debug(f"Geocoding a returnat {len(result)} rezultate:")
            for i, res in enumerate(result[:5]):
                log_debug(f"  [{i}] {res.get('types')}: {res.get('formatted_address', '')[:60]}")
            
            street_name = None
            street_number = None
            locality = None
            neighborhood = None
            
            for res in result:
                components = res.get('address_components', [])
                
                for comp in components:
                    comp_types = comp.get('types', [])
                    
                    if 'route' in comp_types and not street_name:
                        street_name = comp.get('long_name')
                        log_debug(f"  Găsit route: {street_name}")
                    
                    if 'street_number' in comp_types and not street_number:
                        street_number = comp.get('long_name')
                    
                    if 'locality' in comp_types and not locality:
                        locality = comp.get('long_name')
                    
                    if ('neighborhood' in comp_types or 'sublocality' in comp_types or 'sublocality_level_1' in comp_types) and not neighborhood:
                        neighborhood = comp.get('long_name')
                
                if street_name:
                    break
            
            if street_name:
                parts = []
                if street_number:
                    parts.append(f"{street_name} {street_number}")
                else:
                    parts.append(street_name)
                
                if neighborhood and neighborhood != locality:
                    parts.append(neighborhood)
                
                if locality:
                    parts.append(locality)
                
                address = ", ".join(parts)
            else:
                address = result[0].get('formatted_address', 'Adresă necunoscută')
                log_debug("Nu s-a găsit strada în componente, folosim formatted_address")
            
            log_success(f"Adresă găsită: {address}")
            return address
        else:
            return "Adresă necunoscută"
    except Exception as e:
        log_error(f"Eroare la reverse geocoding: {e}")
        return f"Eroare: {e}"


def get_distance_info(origin_coords, destinations):
    """
    Obține informații despre distanță și durată de la origin la multiple destinații.
    Returnează un dicționar cu place_id ca cheie și info despre distanță/durată.
    """
    if not origin_coords or not destinations:
        return {}
    
    try:
        dest_coords = []
        place_ids = []
        for dest in destinations:
            loc = dest.get('geometry', {}).get('location', {})
            if loc.get('lat') and loc.get('lng'):
                dest_coords.append(f"{loc['lat']},{loc['lng']}")
                place_ids.append(dest.get('place_id'))
        
        if not dest_coords:
            return {}
        
        origin_str = f"{origin_coords[0]},{origin_coords[1]}"
        
        log_info(f"Se apelează Distance Matrix API (driving) pentru {len(dest_coords)} destinații...")
        driving_result = gmaps_client.distance_matrix(
            origins=[origin_str],
            destinations=dest_coords,
            mode="driving",
            language="ro"
        )
        
        log_info(f"Se apelează Distance Matrix API (walking) pentru {len(dest_coords)} destinații...")
        walking_result = gmaps_client.distance_matrix(
            origins=[origin_str],
            destinations=dest_coords,
            mode="walking",
            language="ro"
        )
        
        distance_info = {}
        driving_elements = driving_result.get('rows', [{}])[0].get('elements', [])
        walking_elements = walking_result.get('rows', [{}])[0].get('elements', [])
        
        for i, place_id in enumerate(place_ids):
            if i < len(driving_elements) and i < len(walking_elements):
                driving_elem = driving_elements[i]
                walking_elem = walking_elements[i]
                
                if driving_elem.get('status') == 'OK':
                    distance_meters = driving_elem.get('distance', {}).get('value', 0)
                    distance_km = distance_meters / 1000
                    
                    info = {
                        'distance_text': driving_elem.get('distance', {}).get('text', 'N/A'),
                        'distance_km': distance_km,
                        'driving_duration': driving_elem.get('duration', {}).get('text', 'N/A'),
                        'walking_duration': None
                    }
                    
                    if distance_km < 5 and walking_elem.get('status') == 'OK':
                        info['walking_duration'] = walking_elem.get('duration', {}).get('text', 'N/A')
                    
                    distance_info[place_id] = info
                else:
                    distance_info[place_id] = {
                        'distance_text': 'N/A',
                        'distance_km': 0,
                        'driving_duration': 'N/A',
                        'walking_duration': None
                    }
        
        log_success(f"Distance Matrix: s-au obținut informații pentru {len(distance_info)} locuri.")
        return distance_info
        
    except Exception as e:
        log_error(f"Eroare la Distance Matrix API: {e}")
        traceback.print_exc()
        return {}


def get_ai_summary(reviews, place_name):
    """Apelează Gemini API pentru a obține un rezumat al recenziilor."""
    global ai_prompt_var, gemini_model_value
    if not reviews:
        return "Nu există recenzii de analizat."
    
    try:
        model = gemini_model_value
        system_prompt = ai_prompt_var
        
        reviews_text = ""
        for i, review in enumerate(reviews[:400]):
            author = review.get('author_name', 'Anonim')
            rating = review.get('rating', 'N/A')
            text = review.get('text', '')
            reviews_text += f"[{rating}⭐] {author}: {text}\n\n"
        
        log_info(f"Se apelează Gemini API (model: {model})...")
        
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"{system_prompt}\n\nRecenzii pentru '{place_name}':\n\n{reviews_text}"
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1024
            }
        }
        
        response = requests.post(gemini_url, json=payload, headers={"Content-Type": "application/json"})
        
        if response.status_code != 200:
            log_error(f"Eroare Gemini API: {response.status_code} - {response.text}")
            return f"Eroare la apelul API: {response.status_code}"
        
        result = response.json()
        ai_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Nu s-a putut genera rezumatul.')
        
        log_success("Rezumat AI generat cu succes.")
        return ai_text
        
    except Exception as e:
        log_error(f"Eroare la generarea rezumatului AI: {e}")
        return f"Eroare: {e}"


def get_history_info(place_name, place_address):
    """Folosește Gemini pentru a genera o descriere enciclopedică."""
    global gemini_model_value
    log_info(f"Se solicită info istoric pentru: {place_name}")
    
    prompt_istoric = (
        f"Ești un ghid turistic expert și istoric de artă. "
        f"Am nevoie de informații despre locația: '{place_name}' situată în '{place_address}'.\n\n"
        f"Te rog să scrii o prezentare stil 'Wikipedia' sau Enciclopedie care să includă:\n"
        f"1. Scurt istoric (anul construirii, fondatori, evenimente majore) - dacă este aplicabil.\n"
        f"2. Detalii arhitecturale sau semnificație culturală.\n"
        f"3. Curiozități sau legende locale.\n\n"
        f"IMPORTANT: Dacă locația este una comercială obișnuită (ex: o farmacie, un fast-food) "
        f"și nu are importanță istorică, scrie doar o scurtă descriere a utilității ei și atmosfera generală, "
        f"fără să inventezi fapte istorice. Răspunde în limba română."
    )

    try:
        model_name = gemini_model_value
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt_istoric}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 800}
        }
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        if response.status_code != 200:
            return "Eroare la generarea textului."
        
        result = response.json()
        return result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Nu am găsit informații.')
    except Exception as e:
        log_error(f"Eroare Gemini History: {e}")
        return f"Eroare: {e}"


class ClickableLabel(QLabel):
    """QLabel care emite semnale la click și la scroll."""
    clicked = Signal()
    scrolled_up = Signal()   # Semnal nou pentru Zoom In
    scrolled_down = Signal() # Semnal nou pentru Zoom Out
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    # --- NOU: Detectare Scroll Mouse ---
    def wheelEvent(self, event):
        # angleDelta().y() este pozitiv când dai scroll în sus (depărtat de tine)
        # și negativ când dai scroll în jos (spre tine)
        if event.angleDelta().y() > 0:
            self.scrolled_up.emit()
        else:
            self.scrolled_down.emit()
        
        # Acceptăm evenimentul ca să nu se propage mai departe
        event.accept()

class MapBridge(QObject):
    """Podul de comunicare între JavaScript (Harta) și Python."""
    # Semnal pe care îl vom emite când JS ne trimite coordonate
    mapClickedSignal = Signal(float, float)
    # Semnal pentru schimbarea tipului de hartă
    mapTypeChangedSignal = Signal(str)
    # Semnal pentru click pe marker de traseu
    markerClickedSignal = Signal(str, str)
    # Semnal pentru click pe POI (Point of Interest) de pe hartă
    poiClickedSignal = Signal(str)
    # NOU: Semnal pentru adăugare waypoint (punct intermediar)
    waypointAddSignal = Signal(float, float)
    # NOU: Semnal pentru setare zonă de explorare
    setExploreSignal = Signal(float, float)
    # NOU: Semnal pentru setare poziție curentă
    setMyPositionSignal = Signal(float, float)
    # NOU: Semnal sincronizare zoom
    zoomChangedSignal = Signal(int)

    @Slot(int)
    def updateZoomLevel(self, zoom):
        """Primește nivelul de zoom din JS și îl trimite în Python."""
        self.zoomChangedSignal.emit(zoom)

    @Slot(float, float)
    def receiveMapClick(self, lat, lng):
        """Această funcție este apelată direct din JavaScript!"""
        # log_info(f"Click primit din JS: {lat}, {lng}")
        self.mapClickedSignal.emit(lat, lng)
    
    @Slot(str)
    def receiveMapTypeChange(self, map_type):
        """Primește schimbarea tipului de hartă din JavaScript."""
        log_debug(f"Tip hartă schimbat: {map_type}")
        self.mapTypeChangedSignal.emit(map_type)
    
    @Slot(str, str)
    def receiveMarkerClick(self, place_id, name):
        """Primește click pe un marker de traseu din JavaScript."""
        log_info(f"Click pe marker: {name} ({place_id[:30]}...)")
        self.markerClickedSignal.emit(place_id, name)
    
    @Slot(str)
    def receivePOIClick(self, place_id):
        """Primește click pe un POI de pe hartă din JavaScript."""
        log_info(f"Click pe POI: {place_id}")
        self.poiClickedSignal.emit(place_id)
    
    @Slot(float, float)
    def receiveWaypointAdd(self, lat, lng):
        """Primește cerere de adăugare waypoint din JavaScript."""
        log_info(f"Cerere adăugare waypoint: {lat}, {lng}")
        self.waypointAddSignal.emit(lat, lng)
    
    @Slot(float, float)
    def receiveSetExplore(self, lat, lng):
        """Primește cerere de setare zonă explorare din JavaScript."""
        log_info(f"Setare zonă explorare: {lat}, {lng}")
        self.setExploreSignal.emit(lat, lng)
    
    @Slot(float, float)
    def receiveSetMyPosition(self, lat, lng):
        """Primește cerere de setare poziție curentă din JavaScript."""
        log_info(f"Setare poziție curentă: {lat}, {lng}")
        self.setMyPositionSignal.emit(lat, lng)
        
class ReviewsDialog(QDialog):
    """Dialog pentru afișarea recenziilor."""
    def __init__(self, place_id, place_name, parent=None):
        super().__init__(parent)
        self.place_id = place_id
        self.place_name = place_name
        self.stored_reviews = []
        
        self.setWindowTitle(f"Recenzii pentru {place_name}")
        self.resize(600, 500)
        
        # Stiluri pentru dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTextEdit {
                font-size: 11pt;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton {
                font-size: 11pt;
                padding: 8px 16px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton:disabled {
                background-color: #f0f0f0;
                color: #aaa;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        button_frame = QHBoxLayout()
        self.ai_button = QPushButton("✨ Rezumat AI")
        self.ai_button.setEnabled(False)
        self.ai_button.clicked.connect(self.generate_ai_summary)
        button_frame.addWidget(self.ai_button)
        button_frame.addStretch()
        layout.addLayout(button_frame)
        
        self.review_text_widget = QTextEdit()
        self.review_text_widget.setReadOnly(True)
        self.review_text_widget.setText("Se încarcă recenziile...")
        layout.addWidget(self.review_text_widget)
        
        QTimer.singleShot(100, self.load_reviews)
    
    def load_reviews(self):
        try:
            details = gmaps_client.place(place_id=self.place_id, fields=['name', 'review'], language='ro')
            reviews = details.get('result', {}).get('reviews', [])
            self.stored_reviews.extend(reviews)
            
            log_success(f"S-au găsit {len(reviews)} recenzii.")
            final_text = f"Recenzii pentru '{self.place_name}' ({len(reviews)} recenzii cele mai recente):\n"
            final_text += "(Notă: Google Places API returnează maxim 5 recenzii per loc)\n\n"
            
            if not reviews:
                final_text = f"Recenzii pentru '{self.place_name}':\n\n"
                final_text += "Acest loc nu are încă nicio recenzie."
            else:
                for review in reviews:
                    author = review.get('author_name', 'Anonim')
                    rating = review.get('rating', 'N/A')
                    text = review.get('text', 'Fără text.')
                    final_text += f"--- {author} ({rating}⭐) ---\n{text}\n\n"
                
                self.ai_button.setEnabled(True)
            
            self.review_text_widget.setText(final_text)
            
        except Exception as e:
            log_error(f"Eroare la aducerea recenziilor: {e}")
            self.review_text_widget.setText(f"A apărut o eroare: {e}")
    
    def generate_ai_summary(self):
        self.ai_button.setEnabled(False)
        self.ai_button.setText("⏳ Se generează...")
        QApplication.processEvents()
        
        summary = get_ai_summary(self.stored_reviews, self.place_name)
        
        summary_dialog = QDialog(self)
        summary_dialog.setWindowTitle(f"✨ Rezumat AI - {self.place_name}")
        summary_dialog.resize(550, 450)
        
        layout = QVBoxLayout(summary_dialog)
        summary_text = QTextEdit()
        summary_text.setReadOnly(True)
        summary_text.setText(summary)
        layout.addWidget(summary_text)
        
        summary_dialog.exec()
        
        self.ai_button.setEnabled(True)
        self.ai_button.setText("✨ Rezumat AI")

class HistoryDialog(QDialog):
    """Dialog pentru afișarea informațiilor istorice."""
    def __init__(self, place_name, info, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"📖 Despre: {place_name}")
        self.resize(600, 550)
        
        # Stiluri pentru dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTextEdit {
                font-size: 11pt;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        title_label = QLabel(f"Despre {place_name}")
        title_font = QFont("Segoe UI", 14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #333; padding: 10px;")
        layout.addWidget(title_label)
        
        text_area = QTextEdit()
        text_area.setReadOnly(True)
        text_font = QFont("Segoe UI", 11)
        text_area.setFont(text_font)
        text_area.setText(info)
        layout.addWidget(text_area)

class RouteDialog(QDialog):
    """Dialog pentru afișarea traseului."""
    def __init__(self, summary_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plan Traseu")
        self.resize(500, 350)
        
        # Stiluri pentru dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTextEdit {
                font-size: 11pt;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        text_widget.setText(summary_text)
        layout.addWidget(text_widget)


class SettingsDialog(QDialog):
    """Dialog pentru setări."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        global ai_prompt_var, gemini_model_value, saved_locations
        
        self.setWindowTitle("⚙️ Setări")
        self.resize(650, 550)
        
        # Stiluri pentru dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                font-size: 11pt;
                color: #333;
            }
            QLineEdit, QTextEdit {
                font-size: 11pt;
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton {
                font-size: 11pt;
                padding: 8px 16px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QListWidget {
                font-size: 11pt;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        self.notebook = QTabWidget()
        layout.addWidget(self.notebook)
        
        # Tab 1: Setări AI
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        ai_layout.setContentsMargins(10, 10, 10, 10)
        
        model_label = QLabel("Model Gemini:")
        model_label.setFont(QFont("Helvetica", 10, QFont.Bold))
        ai_layout.addWidget(model_label)
        
        self.model_entry = QLineEdit()
        self.model_entry.setText(gemini_model_value)
        ai_layout.addWidget(self.model_entry)
        
        ai_layout.addSpacing(10)
        
        prompt_label = QLabel("Prompt pentru analist AI:")
        prompt_label.setFont(QFont("Helvetica", 10, QFont.Bold))
        ai_layout.addWidget(prompt_label)
        
        self.prompt_text = QTextEdit()
        self.prompt_text.setText(ai_prompt_var)
        ai_layout.addWidget(self.prompt_text)
        
        self.notebook.addTab(ai_tab, "🤖 AI Settings")
        
        # Tab 2: Locații Salvate
        locations_tab = QWidget()
        locations_layout = QVBoxLayout(locations_tab)
        locations_layout.setContentsMargins(10, 10, 10, 10)
        
        add_group = QGroupBox("Adaugă locație nouă:")
        add_group_layout = QVBoxLayout(add_group)
        
        name_frame = QHBoxLayout()
        name_frame.addWidget(QLabel("Nume:"))
        self.new_loc_name = QLineEdit()
        self.new_loc_name.setFixedWidth(150)
        name_frame.addWidget(self.new_loc_name)
        
        name_frame.addWidget(QLabel("Coordonate:"))
        self.new_loc_coords = QLineEdit()
        self.new_loc_coords.setFixedWidth(200)
        name_frame.addWidget(self.new_loc_coords)
        
        fill_btn = QPushButton("📋 Curent")
        fill_btn.clicked.connect(self.fill_current_coords)
        name_frame.addWidget(fill_btn)
        name_frame.addStretch()
        
        add_group_layout.addLayout(name_frame)
        
        add_btn = QPushButton("➕ Adaugă")
        add_btn.clicked.connect(self.add_location)
        add_group_layout.addWidget(add_btn, alignment=Qt.AlignRight)
        
        locations_layout.addWidget(add_group)
        
        list_label = QLabel("Locații salvate:")
        list_label.setFont(QFont("Helvetica", 10, QFont.Bold))
        locations_layout.addWidget(list_label)
        
        self.locations_listbox = QListWidget()
        locations_layout.addWidget(self.locations_listbox)
        
        list_buttons = QHBoxLayout()
        load_btn = QPushButton("📥 Încarcă")
        load_btn.clicked.connect(self.load_location)
        list_buttons.addWidget(load_btn)
        
        delete_btn = QPushButton("🗑️ Șterge")
        delete_btn.clicked.connect(self.delete_location)
        list_buttons.addWidget(delete_btn)
        list_buttons.addStretch()
        
        locations_layout.addLayout(list_buttons)
        
        self.notebook.addTab(locations_tab, "📍 Locații Salvate")
        
        # Tab 3: Diversitate (Advanced Scrollable)
        div_tab = QWidget()
        div_layout = QVBoxLayout(div_tab)
        
        div_label = QLabel("Configurează țintele pentru diversitate (Adăugare Automată):")
        div_label.setStyleSheet("font-weight: bold; color: #555;")
        div_layout.addWidget(div_label)
        
        # Scroll Area pentru că lista e lungă
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Grid pentru controale
        grid_frame = QFrame()
        grid = QGridLayout(grid_frame)
        grid.setSpacing(15)
        
        # Header Table
        grid.addWidget(QLabel("<b>CATEGORIE</b>"), 0, 0)
        grid.addWidget(QLabel("<b>MIN</b>"), 0, 1)
        grid.addWidget(QLabel("<b>MAX</b>"), 0, 2)
        grid.addWidget(QLabel("<b>RATING</b>"), 0, 3)
        
        # Linie separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        grid.addWidget(line, 1, 0, 1, 3)
        
        self.div_widgets = {} 
        
        row = 2
        # Ordinea logică de afișare
        display_order = [
            'restaurant', 'cafe', 'bar',       # Food
            'museum', 'religion', 'tourist',   # Culture
            'park', 'fun',                     # Nature/Fun
            'mall', 'market', 'books',         # Shopping
            'pharmacy', 'bank', 'fuel', 'transport' # Utils
        ]
        
        for cat_key in display_order:
            if cat_key not in CATEGORIES_MAP: continue
            
            cat_data = CATEGORIES_MAP[cat_key]
            # Default fallback dacă nu există în settings
            current_conf = diversity_settings.get(cat_key, {'count': 0, 'min_rating': 4})
            
            # 1. Nume Categorie
            lbl = QLabel(cat_data['label'])
            lbl.setStyleSheet("font-size: 11pt;")
            grid.addWidget(lbl, row, 0)
            
            # 2. Minim (Garanție)
            min_val = current_conf.get('min', current_conf.get('count', 0)) # Fallback la vechiul 'count'
            min_edit = QLineEdit(str(min_val))
            min_edit.setFixedWidth(40)
            min_edit.setAlignment(Qt.AlignCenter)
            if min_val > 0:
                min_edit.setStyleSheet("background-color: #e8f5e9; font-weight: bold;")
            grid.addWidget(min_edit, row, 1)

            # 3. Maxim (Plafon)
            max_val = current_conf.get('max', 10) # Default generos
            max_edit = QLineEdit(str(max_val))
            max_edit.setFixedWidth(40)
            max_edit.setAlignment(Qt.AlignCenter)
            grid.addWidget(max_edit, row, 2)
            
            # 4. Rating (Radio Buttons)
            radio_frame = QWidget()
            radio_layout = QHBoxLayout(radio_frame)
            radio_layout.setContentsMargins(0,0,0,0)
            radio_layout.setSpacing(10)
            
            grp = QButtonGroup(radio_frame)
            r_any = QRadioButton("Oricare")
            r_3 = QRadioButton("3.0+")
            r_4 = QRadioButton("4.0+")
            
            grp.addButton(r_any, 0)
            grp.addButton(r_3, 3)
            grp.addButton(r_4, 4)
            
            radio_layout.addWidget(r_any)
            radio_layout.addWidget(r_3)
            radio_layout.addWidget(r_4)
            
            # Set state
            saved_rating = current_conf.get('min_rating', 4)
            if saved_rating >= 4: r_4.setChecked(True)
            elif saved_rating >= 3: r_3.setChecked(True)
            else: r_any.setChecked(True)
            
            grid.addWidget(radio_frame, row, 3)
            
            # Separator subtil
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet("color: #eee;")
            grid.addWidget(sep, row+1, 0, 1, 4)
            
            self.div_widgets[cat_key] = {
                'min': min_edit,
                'max': max_edit,
                'group': grp
            }
            row += 2
            
        scroll_layout.addWidget(grid_frame)
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        div_layout.addWidget(scroll)
        
        self.notebook.addTab(div_tab, "⚖️ Diversitate")

        # Butoane generale
        button_frame = QHBoxLayout()
        
        reset_btn = QPushButton("Resetează AI")
        reset_btn.clicked.connect(self.reset_defaults)
        button_frame.addWidget(reset_btn)
        
        button_frame.addStretch()
        
        cancel_btn = QPushButton("Anulează")
        cancel_btn.clicked.connect(self.reject)
        button_frame.addWidget(cancel_btn)
        
        save_btn = QPushButton("Salvează și Închide")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        button_frame.addWidget(save_btn)
        
        layout.addLayout(button_frame)
        
        self.refresh_locations_list()
    
    def fill_current_coords(self):
        current = self.main_window.my_coords_entry.text().strip()
        if current:
            self.new_loc_coords.clear()
            self.new_loc_coords.setText(current)
    
    def refresh_locations_list(self):
        global saved_locations
        self.locations_listbox.clear()
        for name, coords in saved_locations.items():
            self.locations_listbox.addItem(f"{name}: {coords}")
    
    def add_location(self):
        global saved_locations
        name = self.new_loc_name.text().strip()
        coords = self.new_loc_coords.text().strip()
        
        if not name:
            log_error("Numele locației este obligatoriu.")
            return
        if not coords:
            log_error("Coordonatele sunt obligatorii.")
            return
        
        if parse_coordinates(coords) is None:
            log_error("Coordonatele nu sunt valide.")
            return
        
        saved_locations[name] = coords
        self.refresh_locations_list()
        self.main_window.refresh_location_combo()
        self.new_loc_name.clear()
        self.new_loc_coords.clear()
        log_success(f"Locația '{name}' a fost adăugată.")
    
    def delete_location(self):
        global saved_locations
        current_item = self.locations_listbox.currentItem()
        if not current_item:
            return
        
        item_text = current_item.text()
        name = item_text.split(":")[0].strip()
        
        if name in saved_locations:
            del saved_locations[name]
            self.refresh_locations_list()
            self.main_window.refresh_location_combo()
            log_info(f"Locația '{name}' a fost ștearsă.")
    
    def load_location(self):
        global saved_locations
        current_item = self.locations_listbox.currentItem()
        if not current_item:
            return
        
        item_text = current_item.text()
        name = item_text.split(":")[0].strip()
        
        if name in saved_locations:
            coords = saved_locations[name]
            self.main_window.my_coords_entry.clear()
            self.main_window.my_coords_entry.setText(coords)
            self.main_window.update_address_from_coords(
                self.main_window.my_coords_entry, 
                self.main_window.my_coords_address_label
            )
            log_success(f"Locația '{name}' a fost încărcată.")
            self.accept()
    
    def reset_defaults(self):
        global ai_prompt_var
        self.model_entry.setText(DEFAULT_GEMINI_MODEL)
        self.prompt_text.clear()
        self.prompt_text.setText(DEFAULT_AI_PROMPT)
        ai_prompt_var = DEFAULT_AI_PROMPT
        log_info("Setările AI au fost resetate la valorile implicite.")
    
    def save_settings(self):
        global ai_prompt_var, gemini_model_value, diversity_settings
        gemini_model_value = self.model_entry.text().strip()
        ai_prompt_var = self.prompt_text.toPlainText().strip()
        
        # Salvare Diversitate
        for cat_key, widgets in self.div_widgets.items():
            try:
                min_val = int(widgets['min'].text().strip())
            except:
                min_val = 0
                
            try:
                max_val = int(widgets['max'].text().strip())
            except:
                max_val = 99
            
            # Validare logică simplă
            if max_val < min_val: max_val = min_val

            # Luăm ID-ul butonului selectat (0, 3 sau 4)
            min_rating = widgets['group'].checkedId()
            if min_rating == -1: min_rating = 0
            
            diversity_settings[cat_key] = {
                'min': min_val,
                'max': max_val,
                'min_rating': min_rating
            }
            
        log_success("Setările au fost salvate.")
        self.accept()


# --- Helper Categorii (Dinamic) ---
# --- Helper Categorii (Dinamic) ---
# --- Helper Categorii (Dinamic) ---
def get_category_label(types_list):
    if not types_list: return "📍 Locație"
    
    for cat_key, data in CATEGORIES_MAP.items():
        if any(t in types_list for t in data['keywords']):
            return data['label']
            
    simple_map = {
        'lodging': '🏨 Hotel/Cazare',
        'parking': '🅿️ Parcare',
        'school': '🎓 Școală',
        'university': '🎓 Universitate',
        'hospital': '🏥 Spital',
        'police': '👮 Poliție',
        'poi_geographic': '🌐 Zonă Activă'
    }
    for t in types_list:
        if t in simple_map: return simple_map[t]

    return "📍 " + types_list[0].replace('_', ' ').capitalize()

class RouteItemWidget(QFrame):
    """Widget V43: Design Final (Compact, Clean, Interactive)."""
    lockChanged = Signal(str, bool)
    
    def __init__(self, place_id, name, address, main_window, index=1, initial_color=None, rating='N/A', reviews_count=0, is_open_status='Program necunoscut', place_types=None, route_info=None, website=None, parent=None):
        super().__init__(parent)
        self.place_id = place_id
        self.place_types = place_types or []
        self.name = name
        self.address = address
        self.rating = rating
        self.reviews_count = reviews_count
        self.is_open_status = is_open_status
        self.route_info = route_info
        self.website = website 
        self.main_window = main_window
        self.index = index
        
        # Stil general: Doar linia de jos, fără borduri interne
        self.setStyleSheet("""
            QFrame { background-color: white; border-bottom: 1px solid #e0e0e0; }
            QLabel { border: none; }
        """)
        # Înălțime compactă
        self.setMinimumHeight(68)
        
        # Layout Principal
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4) 
        layout.setSpacing(5)
        
        # 1. Checkbox
        self.lock_checkbox = QCheckBox()
        self.lock_checkbox.setToolTip("Imobilizează")
        self.lock_checkbox.stateChanged.connect(self.on_lock_changed)
        layout.addWidget(self.lock_checkbox)
        
        # 2. Bulina Index
        self.index_label = QLabel(str(index))
        self.index_label.setFixedSize(24, 24)
        self.index_label.setAlignment(Qt.AlignCenter)
        self.initial_color = initial_color if initial_color else self.get_marker_color(index)
        self.update_index_style(index)
        layout.addWidget(self.index_label)
        
        # 3. Text (Vertical)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0) 
        text_layout.setContentsMargins(2, 0, 0, 0)
        
        # R1: Nume
        self.name_label = ClickableLabel(name)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 12pt; color: #2c3e50; border: none;")
        self.name_label.clicked.connect(self.show_on_map)
        text_layout.addWidget(self.name_label)
        
        # R2: Info Traseu
        cat_text = get_category_label(self.place_types)
        if self.route_info:
            row2_text = f"{cat_text}  ➜  🚶 {self.route_info}"
            row2_style = "color: #2e7d32; font-weight: bold; font-size: 10pt; border: none;"
        else:
            row2_text = cat_text
            row2_style = "color: #7f8c8d; font-size: 10pt; border: none;"
        
        self.info_label = QLabel(row2_text)
        self.info_label.setStyleSheet(row2_style)
        text_layout.addWidget(self.info_label)
        
        # R3: Stats Clickabile + Status
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(8)
        stats_layout.setContentsMargins(0, 1, 0, 0)
        
        rating_val = f"{rating}" if rating != 'N/A' else "-"
        reviews_val = f"{reviews_count}"
        
        stats_html = (f"<span style='color:#f57c00; font-weight:bold;'>⭐ {rating_val}</span>"
                      f"&nbsp;&nbsp;"
                      f"<span style='color:#1976d2; font-weight:bold;'>📝 {reviews_val}</span>")
        
        self.stats_clickable = ClickableLabel(stats_html)
        self.stats_clickable.setCursor(Qt.PointingHandCursor)
        self.stats_clickable.setToolTip("Citește Recenziile")
        self.stats_clickable.clicked.connect(self.open_reviews_dialog)
        stats_layout.addWidget(self.stats_clickable)
        
        self.status_label = QLabel(f"🕒 {is_open_status}")
        self.status_label.setStyleSheet("color: #555; font-size: 10pt; border: none;")
        stats_layout.addWidget(self.status_label)
        
        stats_layout.addStretch()
        text_layout.addLayout(stats_layout)
        
        layout.addLayout(text_layout, 1) 
        
        # 4. Butoane (80x36)
        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(4)
        
        BTN_W = 80
        BTN_H = 36
        
        if self.website:
            web_btn = QPushButton("🌐")
            web_btn.setFixedSize(BTN_W, BTN_H)
            web_btn.setToolTip(f"Website: {self.website}")
            web_btn.setStyleSheet("""
                QPushButton { background-color: #f8f9fa; border: 1px solid #ccc; border-radius: 4px; font-size: 16pt; }
                QPushButton:hover { background-color: #e2e6ea; }
            """)
            web_btn.clicked.connect(self.open_website)
            btns_layout.addWidget(web_btn)
        
        ai_btn = QPushButton("🗣️")
        ai_btn.setFixedSize(BTN_W, BTN_H)
        ai_btn.setToolTip("Analiză AI")
        ai_btn.setStyleSheet("""
            QPushButton { background-color: #e3f2fd; border: 1px solid #90caf9; border-radius: 4px; font-size: 16pt; }
            QPushButton:hover { background-color: #bbdefb; }
        """)
        ai_btn.clicked.connect(lambda: self.generate_ai_summary(ai_btn))
        btns_layout.addWidget(ai_btn)
        
        info_btn = QPushButton("📖")
        info_btn.setFixedSize(BTN_W, BTN_H)
        info_btn.setToolTip("Info Enciclopedice")
        info_btn.setStyleSheet("""
            QPushButton { background-color: #fff3e0; border: 1px solid #ffcc80; border-radius: 4px; font-size: 16pt; }
            QPushButton:hover { background-color: #ffe0b2; }
        """)
        info_btn.clicked.connect(lambda: self.show_history(info_btn))
        btns_layout.addWidget(info_btn)
        
        layout.addLayout(btns_layout)

    def sizeHint(self):
        return QSize(0, 70)

    def update_index_style(self, index):
        self.index_label.setStyleSheet(f"background-color: {self.initial_color}; color: white; border-radius: 12px; font-weight: bold; font-size: 10pt;")
    
    def get_marker_color(self, index):
        colors = ['#4285f4', '#ea4335', '#fbbc05', '#34a853', '#9c27b0', '#ff5722', '#00bcd4', '#e91e63', '#795548', '#607d8b']
        return colors[(index - 1) % 10]

    def on_lock_changed(self, state):
        self.lockChanged.emit(self.place_id, state == Qt.Checked.value)
    
    def is_locked(self):
        return self.lock_checkbox.isChecked()
    
    def set_locked(self, locked):
        self.lock_checkbox.setChecked(locked)
    
    def set_lock_enabled(self, enabled):
        self.lock_checkbox.setEnabled(enabled)
    
    def update_index(self, new_index):
        self.index = new_index
        self.index_label.setText(str(new_index))
        self.index_label.setStyleSheet(f"background-color: {self.initial_color}; color: white; border-radius: 12px; font-weight: bold; font-size: 10pt;")

    def show_on_map(self):
        global route_places_coords
        c = route_places_coords.get(self.place_id)
        if c:
            self.main_window.update_map_image(c['lat'], c['lng'], self.name, None, self.place_id)
            
    def open_website(self):
        self.main_window.open_website(self.place_id, self.name)
        
    def generate_ai_summary(self, btn):
        self.main_window.generate_ai_summary_from_card(self.place_id, self.name, btn)
        
    def show_history(self, btn):
        self.main_window.show_history_window(self.name, self.address, btn)
        
    def open_reviews_dialog(self):
        self.main_window.show_reviews_dialog(self.place_id, self.name)
        
    def set_details(self, txt):
        pass 

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asistent Local v17.1 (PySide6)")
        self.resize(1250, 850)
        
        # Aplicăm stiluri profesionale globale
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11pt;
            }
            QLabel {
                font-size: 11pt;
                color: #333333;
            }
            QLineEdit {
                font-size: 11pt;
                padding: 6px 8px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 2px solid #4a90d9;
            }
            QLineEdit:disabled {
                background-color: #e8e8e8;
                color: #888;
            }
            QTextEdit {
                font-size: 11pt;
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QTextEdit:focus {
                border: 2px solid #4a90d9;
            }
            QPushButton {
                font-size: 11pt;
                padding: 8px 16px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #ffffff;
                color: #333;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #999;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #f0f0f0;
                color: #aaa;
            }
            QRadioButton {
                font-size: 11pt;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox {
                font-size: 10pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QComboBox {
                font-size: 11pt;
                padding: 6px 8px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QComboBox:disabled {
                background-color: #e8e8e8;
                color: #888;
            }
            QGroupBox {
                font-size: 11pt;
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                color: #444;
            }
            QScrollArea {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QTabWidget::pane {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                font-size: 11pt;
                padding: 8px 16px;
                border: 1px solid #ccc;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                background-color: #e8e8e8;
            }
            QTabBar::tab:selected {
                background-color: white;
            }
            QListWidget {
                font-size: 11pt;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Top panel cu controale

        # --- UI MODERN START ---
        top_container = QWidget()
        top_layout = QHBoxLayout(top_container)
        top_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        # GRUP 1
        # --- GRUP 1: CONFIGURARE ZONĂ (V31 - Lat 540px & Butoane 120px) ---
        # --- GRUP 1: CONFIGURARE ZONĂ (V32 - Salvat Extins) ---
        # --- GRUP 1: CONFIGURARE ZONĂ (V33 - Adresă Salvată Activă) ---
        g1 = QGroupBox("1. Configurare Zonă")
        g1.setFixedWidth(460)
        l1 = QVBoxLayout(g1)
        
        gr = QGridLayout()
        self.search_type_group = QButtonGroup(self)
        
        self.radio_my_position = QRadioButton("Lângă mine"); self.radio_my_position.setChecked(True); self.search_type_group.addButton(self.radio_my_position); gr.addWidget(self.radio_my_position,0,0)
        self.radio_explore = QRadioButton("Explorare"); self.search_type_group.addButton(self.radio_explore); gr.addWidget(self.radio_explore,0,1)
        self.radio_saved_location = QRadioButton("Salvat"); self.search_type_group.addButton(self.radio_saved_location); gr.addWidget(self.radio_saved_location,1,0)
        self.radio_text = QRadioButton("Text"); self.search_type_group.addButton(self.radio_text); gr.addWidget(self.radio_text,1,1)
        l1.addLayout(gr)
        
        INPUT_H = 30
        
        # --- CONTAINER: LÂNGĂ MINE ---
        self.c_my = QWidget(); l_my = QVBoxLayout(self.c_my); l_my.setContentsMargins(0,0,0,0)
        h_my = QHBoxLayout(); 
        h_my.addWidget(QLabel("Coord:")) 
        
        self.my_coords_entry = QLineEdit()
        self.my_coords_entry.setFixedHeight(INPUT_H)
        h_my.addWidget(self.my_coords_entry)
        
        self.my_coords_geo_btn = QPushButton("📍 Arată")
        self.my_coords_geo_btn.setFixedSize(120, INPUT_H) 
        self.my_coords_geo_btn.clicked.connect(self.on_my_coords_geo_click)
        h_my.addWidget(self.my_coords_geo_btn)
        
        l_my.addLayout(h_my)
        self.my_coords_address_label = QLabel("")
        self.my_coords_address_label.setStyleSheet("color: #666; font-size: 9pt;")
        l_my.addWidget(self.my_coords_address_label)
        l1.addWidget(self.c_my)
        
        # --- CONTAINER: EXPLORARE ---
        self.c_exp = QWidget(); l_exp = QVBoxLayout(self.c_exp); l_exp.setContentsMargins(0,0,0,0)
        h_exp = QHBoxLayout(); 
        
        self.explore_coords_entry = QLineEdit()
        self.explore_coords_entry.setPlaceholderText("Click pe hartă")
        self.explore_coords_entry.setFixedHeight(INPUT_H)
        h_exp.addWidget(self.explore_coords_entry)
        
        self.explore_geo_btn = QPushButton("📍 Arată")
        self.explore_geo_btn.setFixedSize(120, INPUT_H)
        self.explore_geo_btn.clicked.connect(self.on_explore_geo_click)
        h_exp.addWidget(self.explore_geo_btn)
        
        l_exp.addLayout(h_exp)
        self.explore_address_label = QLabel("")
        self.explore_address_label.setStyleSheet("color: #666; font-size: 9pt;")
        l_exp.addWidget(self.explore_address_label)
        l1.addWidget(self.c_exp)
        
        # --- CONTAINER: SALVAT ---
        self.c_sav = QWidget(); l_sav = QVBoxLayout(self.c_sav); l_sav.setContentsMargins(0,0,0,0)
        
        # 1. Combo Box
        self.location_combo = QComboBox()
        self.location_combo.setFixedHeight(INPUT_H)
        self.location_combo.currentTextChanged.connect(self.on_location_selected)
        l_sav.addWidget(self.location_combo)
        
        # 2. Coordonate + Buton
        h_sav_coords = QHBoxLayout()
        self.saved_coords_entry = QLineEdit()
        self.saved_coords_entry.setPlaceholderText("Coordonate locație...")
        self.saved_coords_entry.setFixedHeight(INPUT_H)
        h_sav_coords.addWidget(self.saved_coords_entry)
        
        self.saved_geo_btn = QPushButton("📍 Arată")
        self.saved_geo_btn.setFixedSize(120, INPUT_H)
        # Cand apesi butonul, centrezi harta
        self.saved_geo_btn.clicked.connect(lambda: self.update_address_and_center_map(self.saved_coords_entry, self.saved_address_label, "Locație Salvată", "saved"))
        h_sav_coords.addWidget(self.saved_geo_btn)
        
        l_sav.addLayout(h_sav_coords)
        
        # 3. Adresă Label (CU STIL CORECT)
        self.saved_address_label = QLabel("")
        self.saved_address_label.setStyleSheet("color: #666; font-size: 9pt;")
        self.saved_address_label.setWordWrap(True)
        l_sav.addWidget(self.saved_address_label)
        
        l1.addWidget(self.c_sav)
        
        # --- RAZĂ ---
        self.c_rad = QWidget(); l_rad = QHBoxLayout(self.c_rad); l_rad.setContentsMargins(0,5,0,0)
        l_rad.addWidget(QLabel("Rază (km):"))
        self.radius_entry = QLineEdit("1.5")
        self.radius_entry.setFixedSize(50, INPUT_H)
        self.radius_entry.setAlignment(Qt.AlignCenter)
        l_rad.addWidget(self.radius_entry)
        
        self.use_my_position_for_distance = QCheckBox("Dist. de la mine")
        l_rad.addWidget(self.use_my_position_for_distance)
        
        l_rad.addStretch() 
        l1.addWidget(self.c_rad)
        
        l1.addStretch()
        
        # Buton Setare Explorare
        self.btn_set_exp = QPushButton("⬇️ Setează Explorare Aici")
        self.btn_set_exp.setFixedHeight(40)
        self.btn_set_exp.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold; font-size: 11pt; border-radius: 4px;")
        self.btn_set_exp.clicked.connect(self.set_map_center_as_explore)
        l1.addWidget(self.btn_set_exp)
        
        def update_vis():
            self.c_my.setVisible(self.radio_my_position.isChecked())
            self.c_exp.setVisible(self.radio_explore.isChecked())
            self.btn_set_exp.setVisible(not self.radio_text.isChecked())
            self.c_sav.setVisible(self.radio_saved_location.isChecked())
            self.c_rad.setVisible(not self.radio_text.isChecked())
        self.search_type_group.buttonClicked.connect(update_vis)
        QTimer.singleShot(10, update_vis)
        
        top_layout.addWidget(g1)
        
        # GRUP 2
        # --- GRUP 2: GENERATOR INTELIGENT (V26 - Inputuri Mai Mari) ---
        # --- GRUP 2: GENERATOR INTELIGENT (V27 - Font Mare & Input Inalt) ---
        # --- GRUP 2: GENERATOR INTELIGENT (V28 - Reorganizat Logic) ---
        # --- GRUP 2: GENERATOR INTELIGENT (V29 - Texte Explicite) ---
        # --- GRUP 2: GENERATOR INTELIGENT (V30 - Inputuri Late 60px) ---
        g2 = QGroupBox("2. Generator Inteligent")
        g2.setFixedWidth(460) 
        l2 = QVBoxLayout(g2)
        l2.setSpacing(8)
        
        # 1. Checkbox Afisare
        self.show_hotspots_checkbox = QCheckBox("Arată zonele interesante pe hartă")
        self.show_hotspots_checkbox.setStyleSheet("font-size: 10pt;")
        self.show_hotspots_checkbox.setChecked(True)
        self.show_hotspots_checkbox.stateChanged.connect(self.toggle_hotspots_visibility)
        l2.addWidget(self.show_hotspots_checkbox)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #ddd;")
        l2.addWidget(line)
        
        STYLE_V_TITLE = "font-weight: bold; font-size: 11pt;"
        INPUT_H = 30
        
        # 2. V1 TOP
        h_v1 = QHBoxLayout()
        self.auto_add_hotspots_checkbox = QCheckBox("[V1] Top")
        self.auto_add_hotspots_checkbox.setStyleSheet(f"color: #1565c0; {STYLE_V_TITLE}")
        h_v1.addWidget(self.auto_add_hotspots_checkbox)
        
        h_v1.addStretch()
        
        # Limita Maximă
        h_v1.addWidget(QLabel("Limită Maximă:"))
        self.auto_add_limit_entry = QLineEdit("15")
        self.auto_add_limit_entry.setFixedSize(35, INPUT_H)
        self.auto_add_limit_entry.setAlignment(Qt.AlignCenter)
        h_v1.addWidget(self.auto_add_limit_entry)
        
        # Minim Reviews (LĂȚIT LA 60px)
        h_v1.addWidget(QLabel("Nr. Minim Reviews:"))
        self.min_reviews_entry = QLineEdit("500")
        self.min_reviews_entry.setFixedSize(60, INPUT_H) 
        self.min_reviews_entry.setAlignment(Qt.AlignCenter)
        h_v1.addWidget(self.min_reviews_entry)
        
        l2.addLayout(h_v1)
        
        # 3. V2 DIVERSITATE
        h_v2 = QHBoxLayout()
        self.diversity_checkbox = QCheckBox("[V2] Diversitate")
        self.diversity_checkbox.setStyleSheet(f"color: #2e7d32; {STYLE_V_TITLE}")
        h_v2.addWidget(self.diversity_checkbox)
        
        h_v2.addStretch()
        
        # Buton Setări
        b_div = QPushButton("⚙️ Setări")
        b_div.setFixedSize(120, 40) 
        b_div.clicked.connect(lambda: self.open_settings())
        h_v2.addWidget(b_div)
        
        l2.addLayout(h_v2)
        
        # 4. V3 POI GEO
        h_v3 = QHBoxLayout()
        self.geo_coverage_checkbox = QCheckBox("[V3] POI Geo")
        self.geo_coverage_checkbox.setStyleSheet(f"color: #e65100; {STYLE_V_TITLE}")
        h_v3.addWidget(self.geo_coverage_checkbox)
        
        h_v3.addStretch()
        
        # Limita Maximă
        h_v3.addWidget(QLabel("Limită Max.:"))
        self.geo_limit_entry = QLineEdit("3")
        self.geo_limit_entry.setFixedSize(35, INPUT_H)
        self.geo_limit_entry.setAlignment(Qt.AlignCenter)
        h_v3.addWidget(self.geo_limit_entry)
        
        # Distanța Minimă (LĂȚIT LA 60px)
        h_v3.addWidget(QLabel("Distanța Min. (m):"))
        self.geo_dist_entry = QLineEdit("500")
        self.geo_dist_entry.setFixedSize(60, INPUT_H)
        self.geo_dist_entry.setAlignment(Qt.AlignCenter)
        h_v3.addWidget(self.geo_dist_entry)
        
        l2.addLayout(h_v3)
        
        l2.addStretch()
        
        # 5. SCANARE
        b_scan = QPushButton("🔥 Scanează și Generează")
        b_scan.setFixedHeight(40)
        b_scan.setStyleSheet("background-color: #ff5722; color: white; font-weight: bold; border-radius: 4px; font-size: 11pt;")
        b_scan.clicked.connect(self.scan_hotspots)
        l2.addWidget(b_scan)
        
        top_layout.addWidget(g2)
        
        # GRUP 3
        # --- GRUP 3: ACȚIUNI MANUALE (Layout Nou V24 Fixed) ---
        # --- GRUP 3: ACȚIUNI MANUALE (V25 - Stars & Big Buttons) ---
        # --- GRUP 3: ACȚIUNI MANUALE (V31 - Lat 540px) ---
        g3 = QGroupBox("3. Acțiuni Manuale")
        g3.setFixedWidth(460) # Lățime mărită
        l3 = QVBoxLayout(g3)
        l3.setSpacing(10) 
        
        # 1. LABEL
        self.prompt_label = QLabel("Introduceți un cuvânt cheie:")
        l3.addWidget(self.prompt_label)
        
        # 2. CĂUTARE (Input + Buton)
        h_src = QHBoxLayout()
        self.prompt_entry = QTextEdit()
        self.prompt_entry.setPlaceholderText("ex: farmacie...")
        # Mărim inputul proporțional cu lățimea grupului
        self.prompt_entry.setFixedSize(350, 38) 
        self.prompt_entry.setStyleSheet("border: 1px solid #ccc; border-radius: 4px;")
        h_src.addWidget(self.prompt_entry)
        
        b_src = QPushButton("🔍")
        b_src.setFixedSize(80, 40) 
        b_src.setStyleSheet("background-color: #4a90d9; color: white; font-size: 16px; border-radius: 4px;")
        b_src.clicked.connect(self.send_request)
        h_src.addWidget(b_src)
        h_src.addStretch()
        l3.addLayout(h_src)
        
        # 3. FILTRE (Sortare)
        self.sort_group = QButtonGroup(self); h_sort = QHBoxLayout(); 
        h_sort.addWidget(QLabel("Sort:"))
        
        self.radio_relevance = QRadioButton("Relevanță")
        self.radio_relevance.setChecked(True)
        self.sort_group.addButton(self.radio_relevance)
        h_sort.addWidget(self.radio_relevance)
        
        self.radio_rating = QRadioButton("Rating")
        self.sort_group.addButton(self.radio_rating)
        h_sort.addWidget(self.radio_rating)
        
        self.radio_distance = QRadioButton("Distanță")
        self.sort_group.addButton(self.radio_distance)
        h_sort.addWidget(self.radio_distance)
        
        l3.addLayout(h_sort)
        
        # 4. FILTRE (Rating)
        self.rating_group = QButtonGroup(self); h_rate = QHBoxLayout(); 
        h_rate.addWidget(QLabel("Min:"))
        
        self.radio_any = QRadioButton("Any")
        self.radio_any.setChecked(True)
        self.rating_group.addButton(self.radio_any)
        h_rate.addWidget(self.radio_any)
        
        self.radio_3plus = QRadioButton("⭐ 3+")
        self.rating_group.addButton(self.radio_3plus)
        h_rate.addWidget(self.radio_3plus)
        
        self.radio_4plus = QRadioButton("⭐ 4+")
        self.rating_group.addButton(self.radio_4plus)
        h_rate.addWidget(self.radio_4plus)
        
        l3.addLayout(h_rate)
        
        # Obiect ascuns
        self.route_total_label = QLineEdit(""); self.route_total_label.setVisible(False) 
        l3.addWidget(self.route_total_label)
        
        l3.addStretch() 
        
        # 5. BUTOANE MICI
        h_small_btns = QHBoxLayout()
        
        b_sav = QPushButton("💾")
        b_sav.setFixedSize(80, 40)
        b_sav.setToolTip("Salvează Traseu")
        b_sav.clicked.connect(self.save_route_to_file)
        h_small_btns.addWidget(b_sav)
        
        b_lod = QPushButton("📂")
        b_lod.setFixedSize(80, 40)
        b_lod.setToolTip("Încarcă Traseu")
        b_lod.clicked.connect(self.load_route_from_file)
        h_small_btns.addWidget(b_lod)
        
        b_ref = QPushButton("🔄")
        b_ref.setFixedSize(80, 40)
        b_ref.setToolTip("Reîmprospătează Info Traseu")
        b_ref.clicked.connect(self.refresh_route_info)
        h_small_btns.addWidget(b_ref)
        
        h_small_btns.addStretch()
        l3.addLayout(h_small_btns)
        
        # 6. BUTON MARE
        b_gen = QPushButton("🗺️ Generează Traseu")
        b_gen.setFixedHeight(45) 
        b_gen.setStyleSheet("background-color: #ff5722; color: white; font-weight: bold; font-size: 12pt; border-radius: 5px;")
        b_gen.clicked.connect(self.generate_optimized_route)
        l3.addWidget(b_gen)
        
        top_layout.addWidget(g3)
        main_layout.addWidget(top_container)
        content_frame = QWidget()
        content_layout = QGridLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Panoul hărții
        map_panel = QWidget()
        map_layout = QVBoxLayout(map_panel)
        map_layout.setContentsMargins(0, 0, 5, 0)
        
        # Header navigare hartă
        map_header = QHBoxLayout()
        map_header.addWidget(QLabel("Navigare Hartă:"))
        
        self.map_search_entry = QLineEdit()
        self.map_search_entry.setFixedWidth(150)
        self.map_search_entry.returnPressed.connect(self.search_location_on_map)
        map_header.addWidget(self.map_search_entry)
        
        go_btn = QPushButton("Mergi")
        go_btn.setStyleSheet("background-color: #eee;")
        go_btn.clicked.connect(self.search_location_on_map)
        map_header.addWidget(go_btn)
        
        map_header.addStretch()
        
        
        map_layout.addLayout(map_header)
        
        # Controale zoom
        zoom_controls = QHBoxLayout()
        
        self.zoom_in_button = QPushButton("Zoom In (+)")
        self.zoom_in_button.setEnabled(False)
        self.zoom_in_button.clicked.connect(self.zoom_in)
        
        self.zoom_out_button = QPushButton("Zoom Out (-)")
        self.zoom_out_button.setEnabled(False)
        self.zoom_out_button.clicked.connect(self.zoom_out)
        
        zoom_controls.addStretch()
        map_layout.addLayout(zoom_controls)
        

        # --- Harta Interactivă (WebEngine) ---
        self.web_view = QWebEngineView()
        
        # 1. Configurăm Pagina Custom (pentru a vedea erorile în consolă)
        self.web_page = WebPage(self.web_view)
        self.web_view.setPage(self.web_page)
        
        # 2. === FIX SECURITATE ===
        # Aplicăm setările direct pe obiectul settings() al paginii
        settings = self.web_page.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        # =========================

        # 3. Configurăm Canalul de Comunicare
        self.channel = QWebChannel()
        self.map_bridge = MapBridge()
        self.map_bridge.mapClickedSignal.connect(self.on_web_map_click) 
        self.map_bridge.mapTypeChangedSignal.connect(self.on_map_type_changed)
        self.map_bridge.markerClickedSignal.connect(self.on_marker_clicked)
        self.map_bridge.poiClickedSignal.connect(self.on_poi_clicked)
        self.map_bridge.waypointAddSignal.connect(self.on_waypoint_add)
        self.map_bridge.setExploreSignal.connect(self.on_set_explore_from_map)
        self.map_bridge.setMyPositionSignal.connect(self.on_set_my_position_from_map)
        # Conectare sincronizare zoom
        self.map_bridge.zoomChangedSignal.connect(self.on_map_zoom_changed)
        self.channel.registerObject("pyObj", self.map_bridge)
        self.web_page.setWebChannel(self.channel) # Punem canalul pe Pagină, nu pe View
        
        # Variabilă pentru tipul de hartă
        self.current_map_type = 'roadmap'
        
        # 4. Încărcăm HTML-ul
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            map_path = os.path.join(script_dir, "map_template.html")

            with open(map_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            
            # Injectare Cheie
            placeholder = "API_KEY_PLACEHOLDER"
            if placeholder in html_content:
                html_content = html_content.replace(placeholder, api_key)
                log_success("Cheia API a fost injectată.")
            else:
                log_warning("Placeholder-ul nu a fost găsit (posibil cheie hardcoded).")

            self.web_view.setHtml(html_content, QUrl.fromLocalFile(map_path))
            
        except Exception as e:
            log_error(f"Nu s-a putut încărca map_template.html: {e}")
            self.web_view.setHtml(f"<h3>Eroare: {e}</h3>")

        map_layout.addWidget(self.web_view, 1)
        
        # --- FIX STARTUP: Așteptăm încărcarea hărții ---
        self.map_is_loaded = False
        self.web_view.loadFinished.connect(self.on_map_ready)

        content_layout.addWidget(map_panel, 0, 0)
        
        # Panoul de rezultate cu taburi
        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(5, 0, 0, 0)
        
        # TabWidget pentru Rezultate și Traseu
        self.results_tabs = QTabWidget()
        self.results_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                font-size: 12pt;
                font-weight: bold;
                padding: 10px 20px;
                border: 1px solid #ccc;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                background-color: #e8e8e8;
            }
            QTabBar::tab:selected {
                background-color: white;
            }
        """)
        
        # Tab 1: Rezultate
        results_tab = QWidget()
        results_tab_layout = QVBoxLayout(results_tab)
        results_tab_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setAlignment(Qt.AlignTop)
        
        scroll_area.setWidget(self.results_widget)
        results_tab_layout.addWidget(scroll_area)
        
        self.results_tabs.addTab(results_tab, "📋 Rezultate")
        # [V46] Conectăm click-ul pe tab pentru a restaura lista
        self.results_tabs.tabBarClicked.connect(self.on_results_tab_clicked)
        
        # Tab 2: Traseu
        route_tab = QWidget()
        route_tab_layout = QVBoxLayout(route_tab)
        route_tab_layout.setContentsMargins(10, 10, 10, 10)
        
        # Instrucțiuni
        instructions_label = QLabel("Trage pentru a reordona. ☑️ = imobilizează (doar consecutiv de sus).")
        instructions_label.setStyleSheet("font-size: 10pt; color: #666; font-style: italic;")
        instructions_label.setWordWrap(True)
        route_tab_layout.addWidget(instructions_label)
        
        # Lista de traseu cu drag & drop
        self.route_list = QListWidget()
        self.route_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.route_list.setDefaultDropAction(Qt.MoveAction)
        self.last_route_order = []  # Salvăm ordinea pentru a detecta schimbările la drag & drop
        self.route_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QListWidget::item {
                padding: 2px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        # Conectăm semnalul pentru când se schimbă ordinea prin drag & drop
        self.route_list.model().rowsMoved.connect(self.on_route_items_moved)
        route_tab_layout.addWidget(self.route_list)
        
        # Butoane pentru gestionarea traseului
        route_buttons_layout = QHBoxLayout()
        
        remove_from_route_btn = QPushButton("🗑️ Elimină selectat")
        remove_from_route_btn.setStyleSheet("""
            QPushButton {
                font-size: 11pt;
                padding: 8px 16px;
                background-color: #ffebee;
                color: #c62828;
                border: 1px solid #ef9a9a;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ffcdd2;
            }
        """)
        remove_from_route_btn.clicked.connect(self.remove_selected_from_route)
        route_buttons_layout.addWidget(remove_from_route_btn)
        
        clear_route_btn = QPushButton("🧹 Golește traseu")
        clear_route_btn.setStyleSheet("""
            QPushButton {
                font-size: 11pt;
                padding: 8px 16px;
                background-color: #fff3e0;
                color: #2e7d32;
                border: 1px solid #ffcc80;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ffe0b2;
            }
        """)
        clear_route_btn.clicked.connect(self.clear_route)
        route_buttons_layout.addWidget(clear_route_btn)
        
        refresh_route_btn = QPushButton("🔄 Refresh Info")
        refresh_route_btn.setStyleSheet("""
            QPushButton {
                font-size: 11pt;
                padding: 8px 16px;
                background-color: #e8f5e9;
                color: #2e7d32;
                border: 1px solid #a5d6a7;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c8e6c9;
            }
        """)
        refresh_route_btn.clicked.connect(self.refresh_route_info)
        route_buttons_layout.addWidget(refresh_route_btn)
        
        # --- NOU: Filtru ComboBox ---
        route_buttons_layout.addSpacing(15)
        self.route_filter_combo = QComboBox()
        self.route_filter_combo.setFixedWidth(160)
        self.route_filter_combo.addItems(["👁️ Ambele", "🏢 Doar Places", "📍 Doar Puncte"])
        self.route_filter_combo.setToolTip("Filtrează lista vizual")
        self.route_filter_combo.currentIndexChanged.connect(self.apply_route_filter)
        route_buttons_layout.addWidget(self.route_filter_combo)
        
        route_buttons_layout.addStretch()
        route_tab_layout.addLayout(route_buttons_layout)
        
        self.results_tabs.addTab(route_tab, "🗺️ Traseu (0)")
        self.results_tabs.addTab(QWidget(), "") # Index 2
        self.results_tabs.setTabEnabled(2, False)
        self.results_tabs.setStyleSheet(self.results_tabs.styleSheet() + " QTabBar::tab:disabled { color: #2e7d32; background: transparent; border: none; font-weight: bold; font-size: 11pt; margin-left: 10px; }")
        self.route_total_label.textChanged.connect(lambda t: self.results_tabs.setTabText(2, t))
        
        results_layout.addWidget(self.results_tabs)
        
        content_layout.addWidget(results_panel, 0, 1)
        
        content_layout.setColumnStretch(0, 1)
        content_layout.setColumnStretch(1, 1)
        
        main_layout.addWidget(content_frame, 1)
        
        # Conectări semnale
        self.search_type_group.buttonClicked.connect(self.update_ui_states)
        self.sort_group.buttonClicked.connect(self.update_ui_states)
        self.my_coords_entry.textChanged.connect(self.update_ui_states)
        
        # Încărcare stare
        self.load_state()
        self.refresh_location_combo()
        self.update_ui_states()
    
    def get_search_type(self):
        if self.radio_my_position.isChecked():
            return "my_position"
        elif self.radio_saved_location.isChecked():
            return "saved_location"
        elif self.radio_explore.isChecked():
            return "explore"
        else:
            return "text"
    
    def set_search_type(self, value):
        if value == "my_position":
            self.radio_my_position.setChecked(True)
        elif value == "saved_location":
            self.radio_saved_location.setChecked(True)
        elif value == "explore":
            self.radio_explore.setChecked(True)
        else:
            self.radio_text.setChecked(True)
    
    def get_sort_type(self):
        if self.radio_relevance.isChecked():
            return "relevance"
        elif self.radio_rating.isChecked():
            return "rating"
        else:
            return "distance"
    
    def set_sort_type(self, value):
        if value == "relevance":
            self.radio_relevance.setChecked(True)
        elif value == "rating":
            self.radio_rating.setChecked(True)
        else:
            self.radio_distance.setChecked(True)
    
    def get_rating_filter(self):
        if self.radio_any.isChecked():
            return "any"
        elif self.radio_3plus.isChecked():
            return "3"
        else:
            return "4"
    
    def set_rating_filter(self, value):
        if value == "any":
            self.radio_any.setChecked(True)
        elif value == "3":
            self.radio_3plus.setChecked(True)
        else:
            self.radio_4plus.setChecked(True)
    
    def update_ui_states(self):
        search_mode = self.get_search_type()
        
        is_nearby_type = search_mode in ["my_position", "saved_location", "explore"]
        
        self.radius_entry.setEnabled(is_nearby_type)
        
        self.my_coords_entry.setEnabled(search_mode == "my_position")
        self.my_coords_geo_btn.setEnabled(search_mode == "my_position")
        
        self.location_combo.setEnabled(search_mode == "saved_location")
        
        self.explore_coords_entry.setEnabled(search_mode == "explore")
        self.explore_geo_btn.setEnabled(search_mode == "explore")
        
        my_coords_filled = len(self.my_coords_entry.text().strip()) > 0
        self.radio_distance.setEnabled(is_nearby_type or my_coords_filled)
        
        if search_mode == "text":
            self.prompt_label.setText("Introduceți ce căutați (ex: restaurante în Cluj):")
        else:
            self.prompt_label.setText("Introduceți un cuvânt cheie (ex: cafenea, farmacie):")
    
    def on_my_coords_geo_click(self):
        self.update_address_and_center_map(
            self.my_coords_entry, 
            self.my_coords_address_label, 
            "Poziția mea", 
            "my_coords"
        )
    
    def on_explore_geo_click(self):
        self.update_address_and_center_map(
            self.explore_coords_entry, 
            self.explore_address_label, 
            "Zona de explorat", 
            "explore_coords"
        )
    
    def update_address_from_coords(self, coords_entry_widget, address_label_widget):
        coords_text = coords_entry_widget.text().strip()
        if not coords_text:
            address_label_widget.setText("")
            return
        
        parsed = parse_coordinates(coords_text)
        if parsed:
            lat, lng = parsed
            address = reverse_geocode(lat, lng)
            if len(address) > 60:
                address = address[:57] + "..."
            address_label_widget.setText(f"📍 {address}")
        else:
            address_label_widget.setText("⚠️ Coordonate invalide")
    
    def update_address_and_center_map(self, coords_entry_widget, address_label_widget, location_name="Locația selectată", address_var_name=None):
        global my_coords_full_address, explore_coords_full_address
        
        coords_text = coords_entry_widget.text().strip()
        if not coords_text:
            address_label_widget.setText("")
            if address_var_name == "my_coords":
                my_coords_full_address = ""
            elif address_var_name == "explore_coords":
                explore_coords_full_address = ""
            return
        
        parsed = parse_coordinates(coords_text)
        if parsed:
            lat, lng = parsed
            address = reverse_geocode(lat, lng)
            
            if address_var_name == "my_coords":
                my_coords_full_address = address
            elif address_var_name == "explore_coords":
                explore_coords_full_address = address
            
            display_address = address
            if len(address) > 60:
                display_address = address[:57] + "..."
            address_label_widget.setText(f"📍 {display_address}")
            
            map_name = address if len(address) <= 40 else address[:37] + "..."
            self.update_map_image(lat, lng, map_name, 15, None)
            log_success(f"Harta a fost centrată pe: {address}")
        else:
            address_label_widget.setText("⚠️ Coordonate invalide")
            if address_var_name == "my_coords":
                my_coords_full_address = ""
            elif address_var_name == "explore_coords":
                explore_coords_full_address = ""
    
    def on_location_selected(self, text):
        global saved_locations
        if text and text in saved_locations:
            coords = saved_locations[text]
            
            # 1. Punem coordonatele în câmp
            if hasattr(self, 'saved_coords_entry'):
                self.saved_coords_entry.setText(coords)
                
                # 2. [V33] Căutăm și afișăm automat adresa (fără să mutăm harta încă)
                if hasattr(self, 'saved_address_label'):
                    # Folosim funcția existentă care face reverse geocoding
                    self.update_address_from_coords(self.saved_coords_entry, self.saved_address_label)
            
            log_info(f"Locația '{text}' selectată: {coords}")

    def refresh_location_combo(self):
        global saved_locations
        self.location_combo.clear()
        self.location_combo.addItems(list(saved_locations.keys()))
        if saved_locations and not self.location_combo.currentText():
            self.location_combo.setCurrentIndex(0)
    
    def open_settings(self):
        dialog = SettingsDialog(self, self)
        dialog.exec()
    
    def search_location_on_map(self):
        query = self.map_search_entry.text().strip()
        if not query:
            return
        
        try:
            log_info(f"Navigare hartă către: {query}")
            geocode_result = gmaps_client.geocode(query, language='ro')
            
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                lat, lng = location['lat'], location['lng']
                formatted_address = geocode_result[0]['formatted_address']
                
                zoom = 15 if any(char.isdigit() for char in query) else 12
                
                self.update_map_image(lat, lng, formatted_address, zoom, None)
                log_success(f"Harta mutată la: {formatted_address}")
            else:
                QMessageBox.warning(self, "Info", "Locația nu a fost găsită.")
                
        except Exception as e:
            log_error(f"Eroare navigare hartă: {e}")
    
    def set_map_center_as_explore(self):
        global current_map_lat, current_map_lng
        
        if current_map_lat is None or current_map_lng is None:
            QMessageBox.warning(self, "Info", "Harta nu este inițializată.")
            return
        
        coords_str = f"{current_map_lat}, {current_map_lng}"
        
        self.explore_coords_entry.setEnabled(True)
        self.explore_coords_entry.clear()
        self.explore_coords_entry.setText(coords_str)
        
        self.radio_explore.setChecked(True)
        
        self.update_address_from_coords(self.explore_coords_entry, self.explore_address_label)
        
        log_success("Centrul hărții a fost setat ca punct de explorare.")
        
        self.explore_coords_entry.setStyleSheet("background-color: #e0f7fa;")
        QTimer.singleShot(500, lambda: self.explore_coords_entry.setStyleSheet(""))
    
    def update_map_image(self, lat, lng, name, zoom=None, place_id=None):
        """Controlează harta interactivă prin JavaScript."""
        global current_map_lat, current_map_lng, current_map_name, current_zoom_level, current_map_place_id
        
        # Gestionare Zoom
        if zoom is not None:
            target_zoom = zoom
        else:
            target_zoom = current_zoom_level if current_zoom_level else 15

        # Actualizăm variabilele globale (ASTA SE FACE MEREU)
        current_map_lat = lat
        current_map_lng = lng
        current_map_name = name
        current_zoom_level = target_zoom
        current_map_place_id = place_id
        
        self.zoom_in_button.setEnabled(True)
        self.zoom_out_button.setEnabled(True)

        # --- FIX: Nu rulăm JS dacă harta nu e gata ---
        if not getattr(self, 'map_is_loaded', False):
            log_info("Harta încă se încarcă. Coordonatele au fost salvate pentru mai târziu.")
            return

        # --- COMANDA CĂTRE JAVASCRIPT ---
        # ... (restul codului rămâne neschimbat: js_code_center etc.) ...
        js_code_center = f"setCenter({lat}, {lng}, {target_zoom});"
        self.web_view.page().runJavaScript(js_code_center)
        
        safe_name = name.replace("'", "\\'").replace('"', '\\"')
        js_code_marker = f"addMarker({lat}, {lng}, '{safe_name}');"
        self.web_view.page().runJavaScript(js_code_marker)
        
        log_success(f"Harta interactivă mutată la: {name}")

    
    def on_map_click(self):
        global current_search_results, current_distance_info, current_map_place_id, current_map_name
        
        if not current_map_place_id:
            log_info("Nu există un loc selectat pe hartă.")
            return
        
        current_place = None
        for place in current_search_results:
            if place.get('place_id') == current_map_place_id:
                current_place = place
                break
        
        if not current_place:
            log_info(f"Se caută detalii pentru place_id: {current_map_place_id}")
            try:
                details = gmaps_client.place(
                    place_id=current_map_place_id, 
                    fields=['name', 'formatted_address', 'rating', 'user_ratings_total', 'opening_hours', 'geometry', 'place_id'],
                    language='ro'
                )
                current_place = details.get('result', {})
                current_place['place_id'] = current_map_place_id
            except Exception as e:
                log_error(f"Nu s-au putut obține detaliile: {e}")
                return
        
        self.clear_results()
        self.create_place_card(current_place, current_distance_info)
        
        dialog = ReviewsDialog(current_map_place_id, current_map_name, self)
        dialog.exec()
        
        log_success(f"S-au afișat detaliile pentru '{current_map_name}'")
    
    def clear_results(self):
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def create_place_card(self, place, distance_info=None):
        global selected_places, route_places_coords
        
        name = place.get('name', 'Fără nume')
        address = place.get('vicinity', place.get('formatted_address', 'Adresă necunoscută'))
        rating = place.get('rating', 'N/A')
        user_ratings_total = place.get('user_ratings_total', 0)
        opening_hours = place.get('opening_hours', {})
        
        if 'open_now' in opening_hours:
            is_open = "Deschis acum" if opening_hours.get('open_now') else "Închis acum"
        else:
            is_open = "Program necunoscut"
        
        place_id = place.get('place_id')
        location = place.get('geometry', {}).get('location', {})
        lat = location.get('lat')
        lng = location.get('lng')
        
        # Salvăm coordonatele pentru traseu
        if place_id and lat and lng:
            route_places_coords[place_id] = {'lat': lat, 'lng': lng, 'name': name}
        
        card = QFrame()
        card.setFrameShape(QFrame.Box)
        card.setStyleSheet("""
            QFrame { 
                border: 1px solid #ddd; 
                border-radius: 6px;
                padding: 4px; 
                margin: 2px; 
                background-color: white;
            }
            QFrame:hover {
                border-color: #4a90d9;
                background-color: #f8f9fa;
            }
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(2)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)
        
        name_label = ClickableLabel(name)
        name_font = QFont("Segoe UI", 18)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setWordWrap(True)
        name_label.setStyleSheet("color: #333; border: none;")
        if place_id and lat and lng:
            name_label.clicked.connect(lambda: self.update_map_image(lat, lng, name, None, place_id))
        header_layout.addWidget(name_label, 1)
        
        # Butoane
        if place_id:
            # Checkbox traseu
            sel_checkbox = QCheckBox()
            sel_checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 26px;
                    height: 26px;
                }
            """)
            if place_id in selected_places:
                sel_checkbox.setChecked(True)
            # Extragem tipurile din 'place' (search result)
            p_types = place.get('types', [])
            sel_checkbox.stateChanged.connect(lambda state, pid=place_id, n=name, r=rating, rc=user_ratings_total, s=is_open, t=p_types: self.toggle_selection(pid, n, r, rc, s, state, t))
            header_layout.addWidget(sel_checkbox)
            
            # Buton Website
            web_btn = QPushButton("🌐")
            web_btn.setFixedSize(48, 44)
            web_btn.setStyleSheet("""
                QPushButton {
                    font-size: 18pt;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: #f8f9fa;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                }
            """)
            web_btn.clicked.connect(lambda: self.open_website(place_id, name))
            header_layout.addWidget(web_btn)
            
            # Buton AI Reviews
            ai_btn = QPushButton("🗣️ Opinii")
            ai_btn.setStyleSheet("""
                QPushButton {
                    font-size: 15pt;
                    padding: 6px 10px;
                    border: 1px solid #b3d9ff;
                    border-radius: 4px;
                    background-color: #e3f2fd;
                    color: #1976d2;
                }
                QPushButton:hover {
                    background-color: #bbdefb;
                }
            """)
            ai_btn.clicked.connect(lambda: self.generate_ai_summary_from_card(place_id, name, ai_btn))
            header_layout.addWidget(ai_btn)
            
            # Buton Wiki/Istorie
            hist_btn = QPushButton("📖 Info")
            hist_btn.setStyleSheet("""
                QPushButton {
                    font-size: 15pt;
                    font-weight: bold;
                    padding: 6px 10px;
                    border: 1px solid #ffe082;
                    border-radius: 4px;
                    background-color: #fff8e1;
                    color: #5d4037;
                }
                QPushButton:hover {
                    background-color: #ffecb3;
                }
            """)
            hist_btn.clicked.connect(lambda: self.show_history_window(name, address, hist_btn))
            header_layout.addWidget(hist_btn)
        
        card_layout.addLayout(header_layout)
        
        # Info line - Rândul 2: Adresă + Rating + Recenzii
        info_layout = QHBoxLayout()
        info_layout.setSpacing(4)
        
        address_label = QLabel(f"📍 {address}")
        address_label.setStyleSheet("font-size: 15pt; color: #555; border: none;")
        info_layout.addWidget(address_label)
        
        rating_label = QLabel(f"  ⭐ {rating}")
        rating_label.setStyleSheet("font-size: 15pt; font-weight: bold; color: #f57c00; border: none;")
        info_layout.addWidget(rating_label)
        
        reviews_label = ClickableLabel(f"({user_ratings_total})")
        reviews_label.setStyleSheet("color: #1976d2; text-decoration: underline; font-size: 15pt; border: none;")
        if place_id:
            reviews_label.clicked.connect(lambda: self.show_reviews_dialog(place_id, name))
        info_layout.addWidget(reviews_label)
        info_layout.addStretch()
        
        card_layout.addLayout(info_layout)
        
        # Status + Distanță + Pe jos - Rândul 3: Totul pe un singur rând
        status_layout = QHBoxLayout()
        status_layout.setSpacing(4)
        
        status_label = QLabel(f"🕒 {is_open}")
        status_label.setStyleSheet("font-size: 15pt; color: #666; border: none;")
        status_layout.addWidget(status_label)
        
        if distance_info and place_id in distance_info:
            dist_data = distance_info[place_id]
            
            # [V47 Fix] Extragere sigură a datelor (evită KeyError)
            # 1. Încercăm formatul standard (Search)
            d_text = dist_data.get('distance_text', 'N/A')
            d_dur = dist_data.get('driving_duration', 'N/A')
            
            # 2. Dacă e format tip POI (nested), suprascriem
            if 'driving' in dist_data:
                d_text = dist_data['driving'].get('distance', d_text)
                d_dur = dist_data['driving'].get('duration', d_dur)

            dist_label = QLabel(f"  🚗 {d_text} • {d_dur}")
            dist_label.setStyleSheet("color: #1976d2; font-size: 15pt; font-weight: bold; border: none;")
            status_layout.addWidget(dist_label)
            
            w_dur = dist_data.get('walking_duration')
            if w_dur:
                walk_label = QLabel(f"  🚶 {w_dur}")
                walk_label.setStyleSheet("color: #388e3c; font-size: 15pt; font-weight: bold; border: none;")
                status_layout.addWidget(walk_label)
        
        status_layout.addStretch()
        card_layout.addLayout(status_layout)
        
        self.results_layout.addWidget(card)
    
    def toggle_selection(self, place_id, name, rating, reviews_count, is_open_status, state, place_types=None, website=None):
        global selected_places
        if state == Qt.Checked.value:
            selected_places[place_id] = {
                'name': name,
                'rating': rating,
                'reviews_count': reviews_count,
                'is_open_status': is_open_status,
                'types': place_types or [],
                'website': website 
            }
            log_info(f"Adăugat la traseu: {name}")
            self.add_to_route_list(place_id, name, "", None, rating, reviews_count, is_open_status, place_types, None, website)
        else:
            if place_id in selected_places:
                del selected_places[place_id]
                log_info(f"Eliminat din traseu: {name}")
                self.remove_from_route_list(place_id)
        
        self.update_route_tab_title()

    def add_to_route_list(self, place_id, name, address="", initial_color=None, rating='N/A', reviews_count=0, is_open_status='Program necunoscut', place_types=None, route_info=None, website=None):
        index = self.route_list.count() + 1
        item = QListWidgetItem()
        item.setData(Qt.UserRole, place_id)
        
        item_widget = RouteItemWidget(place_id, name, address, self, index, initial_color, rating, reviews_count, is_open_status, place_types, route_info, website)
        item_widget.lockChanged.connect(self.on_lock_changed)
        
        item.setSizeHint(item_widget.sizeHint())
        self.route_list.addItem(item)
        self.route_list.setItemWidget(item, item_widget)
        
        self.update_lock_states()
        self.save_route_order()
        self.apply_route_filter()

    def on_route_items_moved(self):
        """Se apelează după drag & drop. Reconstruiește lista pentru a repara widget-urile distruse."""
        # 1. Salvăm NOUA ordine (după drag & drop) și stările
        new_order_ids = []
        saved_colors = {}  # place_id -> initial_color
        saved_locks = {}   # place_id -> is_locked
        
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            place_id = item.data(Qt.UserRole)
            new_order_ids.append(place_id)
            
            # Salvăm culoarea și starea de blocare
            widget = self.route_list.itemWidget(item)
            if widget:
                if hasattr(widget, 'initial_color'):
                    saved_colors[place_id] = widget.initial_color
                saved_locks[place_id] = widget.is_locked()
        
        # Ordinea veche (înainte de drag & drop)
        old_order_ids = self.last_route_order.copy() if self.last_route_order else []
        log_debug(f"[LOCK] Ordine veche: {len(old_order_ids)} elemente, Ordine nouă: {len(new_order_ids)} elemente")
        
        # 2. Golim lista vizuală
        self.route_list.clear()
        
        # 3. Reconstruim lista curată, element cu element, păstrând culorile
        global selected_places
        for place_id in new_order_ids:
            if place_id in selected_places:
                data = selected_places[place_id]
                
                if isinstance(data, dict):
                    name = data.get('name', "Unknown")
                    address = data.get('address', "")
                    rating = data.get('rating', 'N/A')
                    reviews_count = data.get('reviews_count', 0)
                    is_open_status = data.get('is_open_status', 'Program necunoscut')
                    place_types = data.get('types', [])
                else:
                    # Fallback pentru date vechi (doar nume)
                    name = str(data)
                    address = ""
                    rating = 'N/A'
                    reviews_count = 0
                    is_open_status = 'Program necunoscut'
                
                # Reconstruim rândul cu culoarea originală și toate datele
                original_color = saved_colors.get(place_id)
                place_types = data.get('types', []) if isinstance(data, dict) else []
                self.add_to_route_list(place_id, name, address, original_color, rating, reviews_count, is_open_status, place_types)
        
        # 4. Restaurăm bifele inteligent
        # Parcurgem de la început și restaurăm bifele doar pentru elementele 
        # care au rămas pe aceleași poziții consecutive
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            place_id = item.data(Qt.UserRole)
            widget = self.route_list.itemWidget(item)
            
            if not widget:
                break
            
            # Verificăm dacă elementul era pe aceeași poziție înainte
            if i < len(old_order_ids) and old_order_ids[i] == place_id:
                # Elementul e pe aceeași poziție - restaurăm starea de blocare
                if saved_locks.get(place_id, False):
                    widget.set_locked(True)
                    log_debug(f"[LOCK] Restaurat blocare pentru '{widget.name}' (poziția {i+1} neschimbată)")
                else:
                    # Primul element neblocat în ordinea veche oprește lanțul
                    break
            else:
                # Poziția s-a schimbat - oprim restaurarea
                log_debug(f"[LOCK] Stop restaurare la poziția {i+1} - element diferit")
                break
        
        # 5. Actualizăm stările
        self.renumber_route_items()
        self.update_lock_states()
        
        # 6. Salvăm noua ordine pentru următorul drag & drop
        self.save_route_order()
    
    def on_lock_changed(self, place_id, locked):
        """Se apelează când se schimbă starea de blocare a unui element."""
        self.update_lock_states()
    
    def update_lock_states(self):
        """Actualizează starea checkbox-urilor de blocare conform regulii consecutive."""
        # Găsim ultimul element blocat
        last_locked_index = -1
        
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            widget = self.route_list.itemWidget(item)
            if isinstance(widget, RouteItemWidget):
                if widget.is_locked():
                    last_locked_index = i
                else:
                    break  # Primul neblocat oprește căutarea
        
        # Actualizăm starea enabled pentru fiecare checkbox
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            widget = self.route_list.itemWidget(item)
            if isinstance(widget, RouteItemWidget):
                if i == 0:
                    # Primul element poate fi întotdeauna blocat
                    widget.set_lock_enabled(True)
                elif i <= last_locked_index:
                    # Elementele deja blocate rămân enabled
                    widget.set_lock_enabled(True)
                elif i == last_locked_index + 1:
                    # Următorul element după ultimul blocat poate fi blocat
                    widget.set_lock_enabled(True)
                else:
                    # Restul nu pot fi blocate și trebuie debifate
                    widget.set_lock_enabled(False)
                    if widget.is_locked():
                        widget.set_locked(False)
    
    def save_route_order(self):
        """Salvează ordinea curentă a traseului pentru a detecta schimbările la drag & drop."""
        self.last_route_order = []
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            self.last_route_order.append(item.data(Qt.UserRole))
    
    def remove_from_route_list(self, place_id):
        """Elimină o locație din lista de traseu după place_id."""
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            if item.data(Qt.UserRole) == place_id:
                self.route_list.takeItem(i)
                break
        # Renumerotăm elementele rămase
        self.renumber_route_items()
        self.update_lock_states()
        self.save_route_order()
        
        # Reaplicăm filtrul curent pentru ca noul element să respecte regula
        self.apply_route_filter()
    
    def renumber_route_items(self):
        """Renumerotează toate elementele din lista de traseu."""
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            widget = self.route_list.itemWidget(item)
            if isinstance(widget, RouteItemWidget):
                widget.update_index(i + 1)
    
    def reorder_route_list(self, new_order):
        global selected_places
        
        saved_colors = {}
        saved_locks = {}
        
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            pid = item.data(Qt.UserRole)
            w = self.route_list.itemWidget(item)
            if w:
                saved_colors[pid] = getattr(w, 'initial_color', None)
                saved_locks[pid] = w.is_locked()
        
        self.route_list.clear()
        
        for place_id in new_order:
            if place_id in selected_places:
                d = selected_places[place_id]
                
                name = d.get('name', "Unknown")
                addr = d.get('address', "")
                rt = d.get('rating', 'N/A')
                rc = d.get('reviews_count', 0)
                st = d.get('is_open_status', 'Program necunoscut')
                pt = d.get('types', [])
                r_info = d.get('route_info', None)
                web = d.get('website', None)
                
                col = saved_colors.get(place_id)
                self.add_to_route_list(place_id, name, addr, col, rt, rc, st, pt, r_info, web)
                
                last_row = self.route_list.count() - 1
                item = self.route_list.item(last_row)
                w = self.route_list.itemWidget(item)
                if w: w.set_locked(saved_locks.get(place_id, False))
        
        self.update_lock_states()
        self.save_route_order()
        self.apply_route_filter()

    def apply_route_filter(self):
        """Filtrează vizual lista de traseu în funcție de selecția din ComboBox."""
        filter_idx = self.route_filter_combo.currentIndex()
        # 0 = Ambele, 1 = Doar Places, 2 = Doar Puncte Intermediare
        
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            place_id = item.data(Qt.UserRole)
            
            is_waypoint = place_id.startswith("waypoint_")
            should_show = True
            
            if filter_idx == 1 and is_waypoint:
                should_show = False  # Ascunde punctele dacă vrem doar Places
            elif filter_idx == 2 and not is_waypoint:
                should_show = False  # Ascunde Places dacă vrem doar puncte
            
            item.setHidden(not should_show)

    def remove_selected_from_route(self):
        """Elimină locația selectată din traseu."""
        global selected_places
        current_item = self.route_list.currentItem()
        if current_item:
            place_id = current_item.data(Qt.UserRole)
            if place_id in selected_places:
                del selected_places[place_id]
            self.route_list.takeItem(self.route_list.row(current_item))
            self.update_route_tab_title()
            self.renumber_route_items()
            self.update_lock_states()
            self.save_route_order()
            log_info("Locație eliminată din traseu.")
    
    def clear_route(self):
        """Golește tot traseul."""
        global selected_places
        selected_places.clear()
        self.route_list.clear()
        self.update_route_tab_title()
        self.save_route_order()
        self.route_total_label.setVisible(False)
        # [V21 Fix] Curățare corectă (JS încapsulat în string Python)
        log_info("Traseul a fost golit.")
    
        # [V22 Fix] Brute-Force Cleanup (Sterge orice linie existenta)
        js_nuke = ("var targets = ['routePolyline', 'line', 'currentPolyline', 'poly']; ""targets.forEach(function(t){ if(window[t]) { window[t].setMap(null); window[t] = null; } }); ""if(window.routeMarkers) { ""  for(var i=0; i<window.routeMarkers.length; i++) { if(window.routeMarkers[i]) window.routeMarkers[i].setMap(null); } ""  window.routeMarkers = []; ""}")
        self.web_view.page().runJavaScript(js_nuke)
        log_info("Harta a fost curățată forțat (V22).")

    def refresh_route_info(self, silent_mode=False):
        """Actualizează informațiile, PĂSTRÂND etichetele [V1]/[V2] dacă există."""
        global selected_places
        
        is_silent = silent_mode is True
        
        if self.route_list.count() == 0:
            if not is_silent:
                QMessageBox.information(self, "Info", "Nu există locații în traseu.")
            return
        
        if not is_silent:
            reply = QMessageBox.question(
                self, "Actualizare Info", 
                f"Actualizez {self.route_list.count()} locații?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply != QMessageBox.Yes: return
        
        try:
            log_info("Se actualizează informațiile (păstrând prefixele)...")
            
            route_order = []
            saved_colors = {}
            saved_locks = {}
            
            # Salvăm starea curentă
            for i in range(self.route_list.count()):
                item = self.route_list.item(i)
                pid = item.data(Qt.UserRole)
                route_order.append(pid)
                widget = self.route_list.itemWidget(item)
                if widget:
                    if hasattr(widget, 'initial_color'): saved_colors[pid] = widget.initial_color
                    saved_locks[pid] = widget.is_locked()
            
            updated_count = 0
            for place_id in route_order:
                try:
                    details = gmaps_client.place(place_id=place_id, language='ro')
                    result = details.get('result', {})
                    
                    # --- LOGICA DE PĂSTRARE PREFIX ---
                    old_data = selected_places.get(place_id, {})
                    old_name = old_data.get('name', 'Unknown') if isinstance(old_data, dict) else str(old_data)
                    
                    new_google_name = result.get('name', old_name)
                    
                    # Detectăm prefixul [V1], [V2], [V3]
                    prefix = ""
                    if old_name.startswith("[V"):
                        # Luăm primele 5 caractere (ex: "[V1] ")
                        prefix = old_name[:5]
                    
                    # Reconstruim numele final
                    final_name = f"{prefix}{new_google_name}" if prefix and not new_google_name.startswith("[V") else new_google_name
                    
                    rating = result.get('rating', 'N/A')
                    reviews_count = result.get('user_ratings_total', 0)
                    
                    oh = result.get('opening_hours', {})
                    is_open = "Deschis acum" if oh.get('open_now') else "Închis acum" if 'open_now' in oh else "Prog. necunoscut"
                    
                    # Update dict
                    if place_id in selected_places:
                        if isinstance(selected_places[place_id], dict):
                            selected_places[place_id]['name'] = final_name # Numele cu prefix
                            selected_places[place_id]['rating'] = rating
                            selected_places[place_id]['reviews_count'] = reviews_count
                            selected_places[place_id]['is_open_status'] = is_open
                            selected_places[place_id]['types'] = result.get('types', [])
                    
                    updated_count += 1
                    
                except Exception as e:
                    log_error(f"Err update {place_id}: {e}")
                    continue
            
            # Reconstruim lista
            self.route_list.clear()
            for place_id in route_order:
                if place_id in selected_places:
                    d = selected_places[place_id]
                    nm = d.get('name', '?')
                    rt = d.get('rating', 'N/A')
                    rv = d.get('reviews_count', 0)
                    st = d.get('is_open_status', '?')
                    tp = d.get('types', [])
                    
                    col = saved_colors.get(place_id)
                    self.add_to_route_list(place_id, nm, "", col, rt, rv, st, tp)
            
            # Restaurăm lock
            for i in range(self.route_list.count()):
                item = self.route_list.item(i)
                pid = item.data(Qt.UserRole)
                w = self.route_list.itemWidget(item)
                if w and pid in saved_locks and saved_locks[pid]:
                    w.set_locked(True)
            
            self.renumber_route_items()
            self.update_lock_states()
            self.save_route_order()
            self.apply_route_filter()
            
            log_success(f"Info actualizat pentru {updated_count} locații. Prefixele păstrate.")
            
        except Exception as e:
            log_error(f"Err refresh: {e}")
    def save_route_to_file(self):
        """Salvează traseul curent într-un fișier JSON."""
        global selected_places, route_places_coords
        
        if self.route_list.count() == 0:
            QMessageBox.warning(self, "Atenție", "Nu există niciun traseu de salvat!")
            return
        
        # Creăm folderul pentru trasee dacă nu există
        routes_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_routes")
        os.makedirs(routes_folder, exist_ok=True)
        
        # Dialog pentru alegerea numelui fișierului
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvează Traseu",
            routes_folder,
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        # Construim datele pentru salvare
        import time
        route_data = {
            "version": "1.0",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "places": []
        }
        
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            place_id = item.data(Qt.UserRole)
            widget = self.route_list.itemWidget(item)
            
            place_info = {
                "place_id": place_id,
                "name": widget.name if widget else "Unknown",
                "address": widget.address if widget else "",
                "locked": widget.is_locked() if widget else False,
                "initial_color": getattr(widget, 'initial_color', None) if widget else None
            }
            
            # Adăugăm coordonatele dacă le avem
            if place_id in route_places_coords:
                coords = route_places_coords[place_id]
                place_info["lat"] = coords.get("lat")
                place_info["lng"] = coords.get("lng")
            
            route_data["places"].append(place_info)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(route_data, f, ensure_ascii=False, indent=2)
            
            log_success(f"Traseul salvat în: {file_path}")
            QMessageBox.information(self, "Succes", f"Traseul a fost salvat cu succes!\n\n{os.path.basename(file_path)}")
        except Exception as e:
            log_error(f"Eroare la salvarea traseului: {e}")
            QMessageBox.critical(self, "Eroare", f"Nu s-a putut salva traseul:\n{e}")
    
    def load_route_from_file(self):
        """Încarcă un traseu dintr-un fișier JSON."""
        global selected_places, route_places_coords
        
        # Folderul implicit pentru trasee
        routes_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_routes")
        if not os.path.exists(routes_folder):
            routes_folder = os.path.dirname(os.path.abspath(__file__))
        
        # Dialog pentru alegerea fișierului
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Încarcă Traseu",
            routes_folder,
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                route_data = json.load(f)
            
            # Verificăm structura
            if "places" not in route_data:
                raise ValueError("Fișierul nu conține date valide de traseu")
            
            # Întrebăm dacă să înlocuim sau să adăugăm
            if self.route_list.count() > 0:
                reply = QMessageBox.question(
                    self,
                    "Traseu Existent",
                    "Există deja un traseu. Ce doriți să faceți?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.Yes
                )
                reply_text = "Da" if reply == QMessageBox.Yes else ("Nu" if reply == QMessageBox.No else "Anulează")
                
                if reply == QMessageBox.Cancel:
                    return
                elif reply == QMessageBox.Yes:
                    # Înlocuim - golim traseul curent
                    selected_places.clear()
                    self.route_list.clear()
                # Dacă No, adăugăm la traseul existent
            
            # Încărcăm locațiile
            loaded_count = 0
            for place_info in route_data["places"]:
                place_id = place_info["place_id"]
                name = place_info.get("name", "Unknown")
                address = place_info.get("address", "")
                locked = place_info.get("locked", False)
                initial_color = place_info.get("initial_color")
                
                # Adăugăm în dicționarul global
                selected_places[place_id] = {'name': name, 'address': address}
                
                # Adăugăm coordonatele dacă există
                if "lat" in place_info and "lng" in place_info:
                    route_places_coords[place_id] = {
                        'lat': place_info["lat"],
                        'lng': place_info["lng"]
                    }
                
                # Adăugăm în listă cu culoarea originală
                self.add_to_route_list(place_id, name, address, initial_color)
                
                # Restaurăm starea de blocare
                last_row = self.route_list.count() - 1
                item = self.route_list.item(last_row)
                widget = self.route_list.itemWidget(item)
                if widget:
                    widget.set_locked(locked)
                
                loaded_count += 1
            
            self.update_route_tab_title()
            self.update_lock_states()
            self.save_route_order()
            
            log_success(f"Traseu încărcat din: {file_path} ({loaded_count} locații)")
            QMessageBox.information(self, "Succes", f"Traseul a fost încărcat cu succes!\n\n{loaded_count} locații din {os.path.basename(file_path)}")
            
            # Auto-refresh informații (silențios)
            log_info("Se execută auto-refresh informații traseu...")
            QTimer.singleShot(500, lambda: self.refresh_route_info(silent_mode=True))
            
        except Exception as e:
            log_error(f"Eroare la încărcarea traseului: {e}")
            QMessageBox.critical(self, "Eroare", f"Nu s-a putut încărca traseul:\n{e}")
    
    def update_route_tab_title(self):
        """Actualizează titlul tab-ului de traseu cu numărul de locații."""
        count = self.route_list.count()
        self.results_tabs.setTabText(1, f"🗺️ Traseu ({count})")
    
    def get_route_order(self):
        """Returnează lista de place_id-uri în ordinea din listă."""
        order = []
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            place_id = item.data(Qt.UserRole)
            order.append(place_id)
        return order
    
    def get_locked_count(self):
        """Returnează numărul de elemente blocate (consecutive de la început)."""
        count = 0
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            widget = self.route_list.itemWidget(item)
            if isinstance(widget, RouteItemWidget) and widget.is_locked():
                count += 1
            else:
                break
        return count
    
    def show_reviews_dialog(self, place_id, name):
        dialog = ReviewsDialog(place_id, name, self)
        dialog.exec()
    
    def open_website(self, place_id, place_name):
        try:
            log_info(f"Se caută website-ul pentru '{place_name}'...")
            details = gmaps_client.place(place_id=place_id, fields=['website'], language='ro')
            website = details.get('result', {}).get('website')
            
            if website:
                log_success(f"Se deschide: {website}")
                webbrowser.open(website)
            else:
                log_info(f"'{place_name}' nu are website înregistrat.")
                QMessageBox.information(self, "Info", f"'{place_name}'\nnu are website înregistrat.")
        except Exception as e:
            log_error(f"Eroare la obținerea website-ului: {e}")
    
    def generate_ai_summary_from_card(self, place_id, place_name, button):
        # [V39] Doar dezactivăm butonul, NU îi schimbăm textul/iconița
        button.setEnabled(False)
        QApplication.processEvents()
        
        try:
            details = gmaps_client.place(place_id=place_id, fields=['name', 'review'], language='ro')
            reviews = details.get('result', {}).get('reviews', [])
            
            if not reviews:
                QMessageBox.information(self, f"Rezumat AI - {place_name}", 
                                       "Nu există recenzii de analizat pentru acest loc.")
            else:
                summary = get_ai_summary(reviews, place_name)
                
                summary_dialog = QDialog(self)
                summary_dialog.setWindowTitle(f"✨ Rezumat AI - {place_name}")
                summary_dialog.resize(550, 450)
                
                layout = QVBoxLayout(summary_dialog)
                summary_text = QTextEdit()
                summary_text.setReadOnly(True)
                summary_text.setText(summary)
                layout.addWidget(summary_text)
                
                summary_dialog.exec()
                
        except Exception as e:
            log_error(f"Eroare la generarea rezumatului: {e}")
            QMessageBox.critical(self, "Eroare", f"Eroare: {e}")
        
        # Reactivăm butonul la final, intact
        button.setEnabled(True)

    def show_history_window(self, place_name, place_address, button):
        # [V39] Doar dezactivăm butonul, NU îi schimbăm textul/iconița
        button.setEnabled(False)
        QApplication.processEvents()
        
        try:
            info = get_history_info(place_name, place_address)
            dialog = HistoryDialog(place_name, info, self)
            dialog.exec()
        except Exception as e:
            log_error(f"Eroare istoric: {e}")
        
        button.setEnabled(True)

    def generate_optimized_route(self):
        global selected_places, route_places_coords
        
        route_order = self.get_route_order()
        if len(route_order) < 2:
            QMessageBox.critical(self, "Eroare", "Selectează cel puțin 2 locuri!")
            return
            
        for pid in selected_places:
            if 'route_info' in selected_places[pid]:
                del selected_places[pid]['route_info']
        
        locked_count = self.get_locked_count()
        start_id = route_order[0]
        start_coords = None
        if start_id in route_places_coords:
            start_coords = (route_places_coords[start_id]['lat'], route_places_coords[start_id]['lng'])
        
        if not start_coords:
             try:
                d = gmaps_client.place(place_id=start_id, fields=['geometry'])
                l = d['result']['geometry']['location']
                start_coords = (l['lat'], l['lng'])
             except:
                QMessageBox.critical(self, "Eroare", "Nu găsesc startul!")
                return

        start_str = f"{start_coords[0]},{start_coords[1]}"
        
        ids_to_optimize = route_order[1:]
        waypoints = []
        for pid in ids_to_optimize:
            if pid in route_places_coords:
                c = route_places_coords[pid]
                waypoints.append(f"{c['lat']},{c['lng']}")
            elif not pid.startswith('waypoint_'):
                waypoints.append(f"place_id:{pid}")
        
        try:
            log_info("Se calculează traseul PIETONAL...")
            
            do_optimize = (locked_count <= 1)
            
            res = gmaps_client.directions(
                origin=start_str, destination=start_str,
                waypoints=waypoints, optimize_waypoints=do_optimize,
                mode="walking", language='ro'
            )
            
            if res:
                route = res[0]
                final_order = [route_order[0]]
                if do_optimize and 'waypoint_order' in route:
                    for idx in route['waypoint_order']:
                        final_order.append(ids_to_optimize[idx])
                else:
                    final_order.extend(ids_to_optimize)
                
                total_km = 0; total_min = 0
                
                if start_id in selected_places:
                    selected_places[start_id]['route_info'] = "Punct de Plecare"
                
                legs = route['legs']
                for i, leg in enumerate(legs):
                    dist = leg['distance']['text']
                    dur = leg['duration']['text']
                    total_km += leg['distance']['value']
                    total_min += leg['duration']['value']
                    
                    if i < len(final_order) - 1:
                        dest_id = final_order[i+1]
                        if dest_id in selected_places:
                            selected_places[dest_id]['route_info'] = f"{dist}, {dur}"
                            
                # [V37] UPDATE: ORAR + WEBSITE
                log_info("Actualizare detalii (Orar + Website)...")
                for pid in final_order:
                    try:
                        need_update = False
                        curr_stat = selected_places.get(pid, {}).get('is_open_status', 'N/A')
                        curr_web = selected_places.get(pid, {}).get('website', None)
                        
                        if curr_stat == 'N/A' or curr_stat == 'Program necunoscut' or curr_web is None:
                            if not pid.startswith('waypoint_'):
                                d = gmaps_client.place(place_id=pid, fields=['opening_hours', 'website'], language='ro')
                                res_det = d.get('result', {})
                                
                                oh = res_det.get('opening_hours', {})
                                st = "Program necunoscut"
                                if 'open_now' in oh: st = "Deschis acum" if oh['open_now'] else "Închis acum"
                                if pid in selected_places: selected_places[pid]['is_open_status'] = st
                                
                                web = res_det.get('website', "")
                                if pid in selected_places: selected_places[pid]['website'] = web
                    except: pass
                
                self.route_total_label.setText(f"🚶 Pietonal: {total_km/1000:.1f} km • {total_min//60} h {total_min%60} min")
                
                poly = route['overview_polyline']['points'].replace('\\', '\\\\')
                self.web_view.page().runJavaScript(f"drawPolyline('{poly}');")
                
                markers_data = []
                for i, pid in enumerate(final_order):
                    p_data = selected_places.get(pid, {})
                    name = p_data.get('name', f"Punct {i+1}") if isinstance(p_data, dict) else str(p_data)
                    col = None
                    w = self.route_list.itemWidget(self.route_list.item(i))
                    if w: col = getattr(w, 'initial_color', None)
                    lat = None; lng = None
                    if pid in route_places_coords:
                        lat = route_places_coords[pid]['lat']; lng = route_places_coords[pid]['lng']
                    if lat:
                        m = {'lat': lat, 'lng': lng, 'name': name, 'index': i+1, 'place_id': pid}
                        if col: m['color'] = col
                        markers_data.append(m)
                
                if markers_data:
                    self.web_view.page().runJavaScript(f"addRouteMarkers({json.dumps(markers_data)});")
                
                self.reorder_route_list(final_order)
                log_success("Traseu pietonal generat și salvat în DB.")

        except Exception as e:
            log_error(f"Eroare API: {e}")
            QMessageBox.critical(self, "Eroare", str(e))

    def send_request(self):
        global current_search_results, current_distance_info, saved_locations
        
        self.clear_results()
        
        log_info("=" * 20 + " CERERE NOUĂ " + "=" * 20)
        
        search_mode = self.get_search_type()
        query_text = self.prompt_entry.toPlainText().strip()
        
        loading_label = QLabel("Se caută...")
        italic_font = QFont("Helvetica", 10)
        italic_font.setItalic(True)
        loading_label.setFont(italic_font)
        self.results_layout.addWidget(loading_label)
        QApplication.processEvents()
        
        try:
            results = []
            search_coords = None
            origin_coords = None
            
            if search_mode == "my_position":
                log_info("Mod Căutare: Lângă mine")
                coords_text = self.my_coords_entry.text().strip()
                if not coords_text:
                    raise ValueError("Coordonatele poziției tale sunt obligatorii.")
                search_coords = parse_coordinates(coords_text)
                if search_coords is None:
                    raise ValueError("Coordonatele GPS sunt invalide.")
                origin_coords = search_coords
                
            elif search_mode == "saved_location":
                log_info("Mod Căutare: Lângă locație salvată")
                selected_name = self.location_combo.currentText()
                if not selected_name:
                    raise ValueError("Selectează o locație salvată.")
                if selected_name not in saved_locations:
                    raise ValueError(f"Locația '{selected_name}' nu există.")
                
                coords_text = saved_locations[selected_name]
                search_coords = parse_coordinates(coords_text)
                if search_coords is None:
                    raise ValueError(f"Coordonatele pentru '{selected_name}' sunt invalide.")
                log_info(f"Locație selectată: {selected_name} ({coords_text})")
                
                if self.use_my_position_for_distance.isChecked():
                    my_coords_text = self.my_coords_entry.text().strip()
                    if my_coords_text:
                        origin_coords = parse_coordinates(my_coords_text)
                    else:
                        origin_coords = search_coords
                else:
                    origin_coords = search_coords
                    
            elif search_mode == "explore":
                log_info("Mod Căutare: Explorare zonă")
                coords_text = self.explore_coords_entry.text().strip()
                if not coords_text:
                    raise ValueError("Coordonatele zonei de explorat sunt obligatorii.")
                search_coords = parse_coordinates(coords_text)
                if search_coords is None:
                    raise ValueError("Coordonatele GPS sunt invalide.")
                
                if self.use_my_position_for_distance.isChecked():
                    my_coords_text = self.my_coords_entry.text().strip()
                    if my_coords_text:
                        origin_coords = parse_coordinates(my_coords_text)
                    else:
                        origin_coords = search_coords
                else:
                    origin_coords = search_coords
                    
            elif search_mode == "text":
                log_info("Mod Căutare: După Text (Text Search)")
                if not query_text:
                    raise ValueError("Câmpul de căutare nu poate fi gol.")
                my_coords_text = self.my_coords_entry.text().strip()
                if my_coords_text:
                    origin_coords = parse_coordinates(my_coords_text)
            
            if search_mode in ["my_position", "saved_location", "explore"]:
                if not query_text:
                    raise ValueError("Cuvântul cheie este obligatoriu.")
                
                radius_km_text = self.radius_entry.text().strip()
                if not radius_km_text:
                    raise ValueError("Raza este obligatorie.")
                radius_in_meters = int(float(radius_km_text.replace(',', '.')) * 1000)
                
                log_info(f"Căutare la {search_coords} cu rază geometrică: {radius_in_meters}m")
                
                places_result = gmaps_client.places_nearby(
                    location=search_coords, 
                    radius=radius_in_meters, 
                    keyword=query_text, 
                    language='ro'
                )
                results = places_result.get('results', [])
            
            elif search_mode == "text":
                places_result = gmaps_client.places(query=query_text, language='ro')
                results = places_result.get('results', [])
            
            # Filtrare după rating
            min_rating = self.get_rating_filter()
            if min_rating != "any":
                rating_threshold = int(min_rating)
                log_info(f"Se filtrează pentru rating >= {rating_threshold}")
                results = [p for p in results if p.get('rating', 0) >= rating_threshold]
            
            if self.get_sort_type() == "rating":
                log_info("Se sortează local după rating (descrescător)")
                results.sort(key=lambda p: p.get('rating', 0), reverse=True)
            
            # Calcul distanțe
            distance_info = {}
            if origin_coords and results:
                loading_label.setText("Se calculează distanțele...")
                QApplication.processEvents()
                distance_info = get_distance_info(origin_coords, results)
            
            # Filtrare strictă pe baza distanței rutiere
            if search_mode in ["my_position", "saved_location", "explore"] and distance_info:
                try:
                    radius_limit_km = float(self.radius_entry.text().replace(',', '.'))
                    log_info(f"Aplicare filtru strict: Eliminare rezultate cu distanța rutieră > {radius_limit_km} km")
                    
                    strict_results = []
                    excluded_count = 0
                    
                    for p in results:
                        pid = p.get('place_id')
                        
                        if pid in distance_info:
                            dist_km = distance_info[pid].get('distance_km', 0)
                            
                            if dist_km <= radius_limit_km:
                                strict_results.append(p)
                            else:
                                excluded_count += 1
                        else:
                            strict_results.append(p)
                    
                    if excluded_count > 0:
                        log_info(f"S-au eliminat {excluded_count} locații care depășeau raza rutieră.")
                        results = strict_results
                        
                except ValueError:
                    pass
            
            # Sortare finală după distanță
            if self.get_sort_type() == "distance" and distance_info:
                log_info("Se sortează local după distanță (crescător)")
                results.sort(key=lambda p: distance_info.get(p.get('place_id'), {}).get('distance_km', float('inf')))
            
            # Afișare rezultate
            loading_label.deleteLater()
            log_success(f"S-au găsit și procesat {len(results)} rezultate finale.")
            
            current_search_results = results
            current_distance_info = distance_info
            
            if not results:
                no_results_label = QLabel("Niciun rezultat găsit în raza specificată.")
                no_results_label.setStyleSheet("color: red; padding: 10px;")
                self.results_layout.addWidget(no_results_label)
                
                # Nu mai avem ce să curățăm la hartă (map_label nu exista), 
                # și nu vrem să ascundem harta web, doar o lăsăm așa cum e.
                
                # Opțional: Dezactivăm butoanele de zoom doar dacă vrei
                # self.zoom_in_button.setEnabled(False)
                # self.zoom_out_button.setEnabled(False)
            else:
                # [V45] Actualizare titlu tab cu număr rezultate
                self.results_tabs.setTabText(0, f"📋 Rezultate ({len(results)})")
                
                # [V45] Curățăm eventuale buline vechi de la scanări/căutări anterioare
                self.web_view.page().runJavaScript("clearHotspots();")
                
                # [V45] Colectăm datele pentru a le afișa pe hartă (buline aurii)
                search_hotspots = []
                
                for place in results:
                    # Creăm cardul în listă
                    self.create_place_card(place, distance_info)
                    
                    # Extragem datele pentru marker vizual
                    loc = place.get('geometry', {}).get('location', {})
                    if loc:
                        search_hotspots.append({
                            'place_id': place.get('place_id'),
                            'name': place.get('name'),
                            'lat': loc['lat'],
                            'lng': loc['lng'],
                            'rating': place.get('rating', 0),
                            'reviews': place.get('user_ratings_total', 0),
                            'types': place.get('types', [])
                        })
                
                # [V45] Trimitem bulinele către hartă fără a muta camera (teleportare eliminată)
                if search_hotspots:
                    js_code = f"addHotspotMarkers({json.dumps(search_hotspots)});"
                    self.web_view.page().runJavaScript(js_code)
                    # Activăm checkbox-ul ca utilizatorul să știe că sunt afișate
                    self.show_hotspots_checkbox.setChecked(True)
            
        except Exception as e:
            log_error(f"O eroare a apărut: {e}")
            traceback.print_exc()
            self.clear_results()
            error_label = QLabel(f"A apărut o eroare: {e}")
            self.results_layout.addWidget(error_label)
    
    def save_state(self):
        global my_coords_full_address, explore_coords_full_address, gemini_model_value, ai_prompt_var, saved_locations
        global current_map_lat, current_map_lng, current_map_name, current_zoom_level, current_map_place_id, selected_places
        global route_places_coords
        
        # 1. Construim lista detaliată a traseului pentru salvare
        saved_route_data = []
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            widget = self.route_list.itemWidget(item)
            if isinstance(widget, RouteItemWidget):
                route_item = {
                    "place_id": widget.place_id,
                    "name": widget.name,
                    "address": widget.address,
                    "locked": widget.is_locked(), # Salvăm dacă era bifat
                    "initial_color": getattr(widget, 'initial_color', None)
                }
                # Salvăm coordonatele dacă le avem (important pentru waypoints custom!)
                if widget.place_id in route_places_coords:
                    coords = route_places_coords[widget.place_id]
                    route_item["lat"] = coords.get("lat")
                    route_item["lng"] = coords.get("lng")
                
                saved_route_data.append(route_item)

        state = {
            "search_query": self.prompt_entry.toPlainText().strip(),
            "my_coords": self.my_coords_entry.text().strip(),
            "my_coords_address": my_coords_full_address,
            "explore_coords": self.explore_coords_entry.text().strip(),
            "explore_coords_address": explore_coords_full_address,
            "selected_location": self.location_combo.currentText(),
            "radius_km": self.radius_entry.text().strip(),
            "search_type": self.get_search_type(),
            "sort_by": self.get_sort_type(),
            "min_rating": self.get_rating_filter(),
            "use_my_position_for_distance": self.use_my_position_for_distance.isChecked(),
            "map_state": {
                "lat": current_map_lat,
                "lng": current_map_lng,
                "name": current_map_name,
                "zoom": current_zoom_level,
                "place_id": current_map_place_id,
                "map_type": self.current_map_type
            },
            "ai_settings": {
                "model": gemini_model_value,
                "prompt": ai_prompt_var
            },
            "diversity_settings": diversity_settings,
            "saved_locations": saved_locations,
            "saved_route": saved_route_data, 
            "route_filter_index": self.route_filter_combo.currentIndex(),
            # --- BIFE SCANARE ---
            "auto_add_enabled": self.auto_add_hotspots_checkbox.isChecked(),
            "auto_add_limit": self.auto_add_limit_entry.text(),
            "diversity_enabled": self.diversity_checkbox.isChecked(),
            "geo_enabled": self.geo_coverage_checkbox.isChecked(),
            "geo_limit": self.geo_limit_entry.text(),
            "geo_dist": self.geo_dist_entry.text()
        }
        
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f, indent=4)
            log_success(f"Starea completă (inclusiv traseul) salvată în {STATE_FILE}")
        except Exception as e:
            log_error(f"Nu s-a putut salva starea: {e}")

    def load_state(self):
        global my_coords_full_address, explore_coords_full_address, gemini_model_value, ai_prompt_var, saved_locations, selected_places
        # --- MODIFICARE: Importăm și variabilele globale de hartă pentru a le seta direct ---
        global current_map_lat, current_map_lng, current_map_name, current_zoom_level, current_map_place_id
        global route_places_coords
        
        if not os.path.exists(STATE_FILE):
            return
        
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            
            # --- Încărcare câmpuri standard ---
            self.prompt_entry.setText(state.get("search_query", ""))
            self.my_coords_entry.setText(state.get("my_coords", ""))
            self.explore_coords_entry.setText(state.get("explore_coords", ""))
            self.radius_entry.setText(state.get("radius_km", "1.5"))
            self.set_search_type(state.get("search_type", "my_position"))
            self.set_sort_type(state.get("sort_by", "relevance"))
            self.set_rating_filter(state.get("min_rating", "any"))
            self.use_my_position_for_distance.setChecked(state.get("use_my_position_for_distance", False))
            
            # Adrese
            if state.get("my_coords_address"):
                my_coords_full_address = state.get("my_coords_address")
                self.my_coords_address_label.setText(f"📍 {my_coords_full_address[:60]}...")
            if state.get("explore_coords_address"):
                explore_coords_full_address = state.get("explore_coords_address")
                self.explore_address_label.setText(f"📍 {explore_coords_full_address[:60]}...")
            
            # --- HARTA (MODIFICAT PENTRU STABILITATE) ---
            map_state = state.get("map_state", {})
            if map_state.get("lat"):
                # Setăm DOAR variabilele globale. Nu apelăm update_map_image() aici!
                # Harta se va actualiza automat via 'on_map_ready' când browserul termină de încărcat HTML-ul.
                current_map_lat = map_state.get("lat")
                current_map_lng = map_state.get("lng")
                current_map_name = map_state.get("name")
                current_zoom_level = map_state.get("zoom", 15)
                current_map_place_id = map_state.get("place_id")
            
            # Restaurăm tipul de hartă
            self.current_map_type = map_state.get("map_type", "roadmap")
            
            # Setări AI & Locații
            if state.get("ai_settings"):
                gemini_model_value = state["ai_settings"].get("model", DEFAULT_GEMINI_MODEL)
                ai_prompt_var = state["ai_settings"].get("prompt", DEFAULT_AI_PROMPT)
            
            global diversity_settings
            if state.get("diversity_settings"):
                diversity_settings = state.get("diversity_settings")
            
            saved_locations = state.get("saved_locations", {})
            self.refresh_location_combo()
            self.location_combo.setCurrentText(state.get("selected_location", ""))
            
            # --- Restaurare Traseu ---
            saved_route = state.get("saved_route", [])
            
            # Resetăm lista globală și UI
            selected_places = {}
            self.route_list.clear()
            
            if saved_route:
                log_info(f"Se restaurează traseul cu {len(saved_route)} puncte...")
                
                for item_data in saved_route:
                    pid = item_data["place_id"]
                    name = item_data["name"]
                    addr = item_data.get("address", "") 
                    locked = item_data.get("locked", False)
                    initial_color = item_data.get("initial_color")
                    
                    # 1. Refacem dicționarul global
                    selected_places[pid] = {'name': name, 'address': addr}
                    
                    # 2. Restaurăm coordonatele (important pentru waypoints custom!)
                    if "lat" in item_data and "lng" in item_data:
                        route_places_coords[pid] = {
                            'lat': item_data["lat"],
                            'lng': item_data["lng"],
                            'name': name
                        }
                    
                    # 3. Adăugăm în listă
                    self.add_to_route_list(pid, name, addr, initial_color)
                    
                    # 4. Restaurăm starea de blocare
                    last_row = self.route_list.count() - 1
                    item = self.route_list.item(last_row)
                    widget = self.route_list.itemWidget(item)
                    if widget:
                        widget.set_locked(locked)
                
                self.update_route_tab_title()
                self.update_lock_states()
            
            # Restaurăm filtrul
            filter_idx = state.get("route_filter_index", 0)
            self.route_filter_combo.setCurrentIndex(filter_idx)
            self.apply_route_filter()
            
            # Restaurăm bifele de scanare
            if "auto_add_enabled" in state:
                self.auto_add_hotspots_checkbox.setChecked(state["auto_add_enabled"])
            if "auto_add_limit" in state:
                self.auto_add_limit_entry.setText(str(state["auto_add_limit"]))
            if "diversity_enabled" in state:
                self.diversity_checkbox.setChecked(state["diversity_enabled"])
                # [V19 Fix] Încărcare stare V3 (Geo Coverage)
                if "geo_enabled" in state:
                    self.geo_coverage_checkbox.setChecked(state["geo_enabled"])
                if "geo_limit" in state:
                    self.geo_limit_entry.setText(str(state["geo_limit"]))
                if "geo_dist" in state:
                    self.geo_dist_entry.setText(str(state["geo_dist"]))
            
            log_success("Starea a fost încărcată complet.")
            
        except Exception as e:
            log_error(f"Eroare la încărcarea stării: {e}")
            traceback.print_exc()
    
    def on_map_ready(self, success):
        """Se apelează automat când pagina HTML s-a încărcat complet."""
        if not success:
            log_error("Harta nu s-a putut încărca în WebEngine.")
            return
            
        self.map_is_loaded = True
        
        # --- INJECTARE JS PENTRU SINCRONIZARE ZOOM ---
        # Asta face ca atunci când dai zoom din mouse, Python să afle imediat
        js_zoom_listener = """
        if (typeof map !== 'undefined') {
            map.addListener('zoom_changed', function() {
                if (window.pyObj) {
                    window.pyObj.updateZoomLevel(map.getZoom());
                }
            });
        }
        """
        self.web_view.page().runJavaScript(js_zoom_listener)
        
        log_success("Browserul a terminat de încărcat harta. Aplicăm starea inițială.")
        
        # Dacă avem coordonate salvate, acum e momentul să mutăm harta
        global current_map_lat, current_map_lng, current_map_name, current_zoom_level, current_map_place_id
        
        if current_map_lat and current_map_lng:
            # Apelăm update_map_image care acum va funcționa pentru că self.map_is_loaded e True
            self.update_map_image(
                current_map_lat, 
                current_map_lng, 
                current_map_name or "Locație Salvată", 
                current_zoom_level, 
                current_map_place_id
            )
        
        # Restaurăm tipul de hartă (roadmap, satellite, terrain, hybrid)
        if hasattr(self, 'current_map_type') and self.current_map_type:
            js_code = f"setMapType('{self.current_map_type}');"
            self.web_view.page().runJavaScript(js_code)
            log_info(f"Tip hartă restaurat: {self.current_map_type}")


    def zoom_in(self):
        """Trimite comandă JavaScript pentru Zoom In."""
        self.web_view.page().runJavaScript("map.setZoom(map.getZoom() + 1);")
    
    def zoom_out(self):
        """Trimite comandă JavaScript pentru Zoom Out."""
        self.web_view.page().runJavaScript("map.setZoom(map.getZoom() - 1);")

    def show_map_context_menu(self, pos):
        """Afișează meniul de click dreapta pe hartă."""
        if not current_map_lat:
            return

        # 1. Calculăm coordonatele punctului unde s-a dat click
        lat, lng = self.get_lat_lng_from_pixel(pos.x(), pos.y())
        
        if lat is None:
            return

        coord_text = f"{lat:.6f}, {lng:.6f}"

        # 2. Creăm meniul
        menu = QMenu(self)
        
        # Acțiunea de copiere
        copy_action = QAction(f"📋 Copiază: {coord_text}", self)
        copy_action.triggered.connect(lambda: self.copy_coords_to_clipboard(coord_text))
        menu.addAction(copy_action)
        
        # Acțiunea de "Setează ca punct de explorare" direct
        set_explore_action = QAction("📍 Setează ca Zonă Explorare", self)
        set_explore_action.triggered.connect(lambda: self.quick_set_explore(coord_text))
        menu.addAction(set_explore_action)

        # 3. Afișăm meniul la poziția mouse-ului
        menu.exec(self.map_label.mapToGlobal(pos))

    def copy_coords_to_clipboard(self, text):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        log_success(f"Copiat în clipboard: {text}")

    def quick_set_explore(self, coords_text):
        """Scurtătură pentru a pune coordonatele direct în câmpul de explorare ȘI A ACTUALIZA HARTA."""
        
        # 1. Punem textul în câmp
        self.explore_coords_entry.setText(coords_text)
        
        # 2. Activăm butonul radio corect
        self.set_search_type("explore")
        
        # 3. --- MODIFICARE AICI ---
        # Înainte apelam update_address_from_coords (doar text).
        # Acum apelăm update_address_and_center_map (text + imagine hartă + marker roșu).
        
        self.update_address_and_center_map(
            self.explore_coords_entry,   # De unde ia coordonatele
            self.explore_address_label,  # Unde scrie adresa
            "Zona de explorat",          # Numele pentru log
            "explore_coords"             # Variabila de stare
        )
        
        log_success("Zona de explorare actualizată și centrată din click dreapta.")

    def on_web_map_click(self, lat, lng):
        """Se execută când dai click pe harta web."""
        log_info(f"Click pe hartă la: {lat}, {lng}")
        
        # Creăm un meniu contextual la poziția cursorului mouse-ului
        menu = QMenu(self)
        
        coord_text = f"{lat:.6f}, {lng:.6f}"
        
        # Acțiunea 1: Copiază
        copy_action = QAction(f"📋 Copiază: {coord_text}", self)
        copy_action.triggered.connect(lambda: self.copy_coords_to_clipboard(coord_text))
        menu.addAction(copy_action)
        
        # Acțiunea 2: Setează explorare
        explore_action = QAction("📍 Setează ca Zonă Explorare", self)
        explore_action.triggered.connect(lambda: self.quick_set_explore(coord_text))
        menu.addAction(explore_action)
        
        # Afișăm meniul la poziția cursorului
        menu.exec(QCursor.pos())

    def on_map_type_changed(self, map_type):
        """Se execută când se schimbă tipul de hartă (roadmap, satellite, terrain, hybrid)."""
        self.current_map_type = map_type
        log_info(f"Tip hartă salvat: {map_type}")
    
    def on_marker_clicked(self, place_id, name):
        """Se execută când se dă click pe un marker de traseu."""
        log_info(f"Afișare detalii pentru: {name}")
        
        # Schimbăm pe tab-ul Rezultate
        self.results_tabs.setCurrentIndex(0)
        
        # Obținem detalii despre loc
        try:
            details = gmaps_client.place(
                place_id=place_id, 
                fields=['name', 'formatted_address', 'rating', 'user_ratings_total', 
                        'opening_hours', 'formatted_phone_number', 'website', 'types'],
                language='ro'
            )
            
            result = details.get('result', {})
            
            # Construim widget-ul cu informații
            self.clear_results()
            
            # Container pentru rezultat
            result_frame = QFrame()
            result_frame.setStyleSheet("""
                QFrame {
                    background-color: #fff3e0;
                    border: 2px solid #ff9800;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 5px;
                }
            """)
            result_layout = QVBoxLayout(result_frame)
            
            # Titlu
            title_label = QLabel(f"📍 {result.get('name', name)}")
            title_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #2e7d32;")
            title_label.setWordWrap(True)
            result_layout.addWidget(title_label)
            
            # Adresă
            if result.get('formatted_address'):
                addr_label = QLabel(f"📫 {result['formatted_address']}")
                addr_label.setStyleSheet("font-size: 11pt; color: #555;")
                addr_label.setWordWrap(True)
                result_layout.addWidget(addr_label)
            
            # Rating
            if result.get('rating'):
                rating = result['rating']
                total = result.get('user_ratings_total', 0)
                stars = "⭐" * int(rating)
                rating_label = QLabel(f"{stars} {rating} ({total} recenzii)")
                rating_label.setStyleSheet("font-size: 11pt; color: #333;")
                result_layout.addWidget(rating_label)
            
            # Tipuri
            if result.get('types'):
                types_text = ", ".join([t.replace('_', ' ').title() for t in result['types'][:3]])
                types_label = QLabel(f"🏷️ {types_text}")
                types_label.setStyleSheet("font-size: 10pt; color: #666;")
                result_layout.addWidget(types_label)
            
            # Telefon
            if result.get('formatted_phone_number'):
                phone_label = QLabel(f"📞 {result['formatted_phone_number']}")
                phone_label.setStyleSheet("font-size: 10pt; color: #333;")
                result_layout.addWidget(phone_label)
            
            # Program
            if result.get('opening_hours'):
                is_open = result['opening_hours'].get('open_now')
                status = "🟢 Deschis acum" if is_open else "🔴 Închis acum"
                hours_label = QLabel(status)
                hours_label.setStyleSheet("font-size: 10pt; font-weight: bold;")
                result_layout.addWidget(hours_label)
            
            # Butoane
            buttons_layout = QHBoxLayout()
            
            # Buton Recenzii
            reviews_btn = QPushButton("🗣️ Recenzii")
            reviews_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e3f2fd;
                    padding: 8px 16px;
                    border: 1px solid #90caf9;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #bbdefb;
                }
            """)
            reviews_btn.clicked.connect(lambda: self.show_reviews_dialog(place_id, name))
            buttons_layout.addWidget(reviews_btn)
            
            # Buton Website
            if result.get('website'):
                web_btn = QPushButton("🌐 Website")
                web_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f3e5f5;
                        padding: 8px 16px;
                        border: 1px solid #ce93d8;
                        border-radius: 4px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #e1bee7;
                    }
                """)
                website_url = result['website']
                web_btn.clicked.connect(lambda: webbrowser.open(website_url))
                buttons_layout.addWidget(web_btn)
            
            buttons_layout.addStretch()
            result_layout.addLayout(buttons_layout)
            
            self.results_layout.addWidget(result_frame)
            self.results_layout.addStretch()
            
            log_success(f"Detalii afișate pentru: {name}")
            
        except Exception as e:
            log_error(f"Eroare la obținerea detaliilor: {e}")
            self.clear_results()
            error_label = QLabel(f"❌ Nu s-au putut obține detaliile pentru {name}")
            error_label.setStyleSheet("color: red; padding: 20px;")
            self.results_layout.addWidget(error_label)
    
    def show_reviews_dialog(self, place_id, name):
        """Afișează dialogul cu recenzii."""
        dialog = ReviewsDialog(place_id, name, self)
        dialog.exec()
    
    def on_poi_clicked(self, place_id):
        """Se execută când se dă click pe un POI de pe hartă (ex: restaurant, magazin, etc.)."""
        log_info(f"Se încarcă detalii pentru POI: {place_id}")
        
        # Schimbăm pe tab-ul Rezultate
        self.results_tabs.setCurrentIndex(0)
        
        try:
            # Obținem detalii despre loc
            details = gmaps_client.place(
                place_id=place_id, 
                fields=['name', 'formatted_address', 'geometry', 'rating', 'user_ratings_total', 
                        'opening_hours', 'formatted_phone_number', 'website', 'type', 'price_level', 'vicinity'],
                language='ro'
            )
            
            result = details.get('result', {})
            name = result.get('name', 'Loc necunoscut')
            
            # Salvăm coordonatele
            global route_places_coords
            loc = result.get('geometry', {}).get('location', {})
            if loc:
                route_places_coords[place_id] = {'lat': loc['lat'], 'lng': loc['lng']}
            
            # Golim rezultatele anterioare
            self.clear_results()
            
            # Creăm card-ul cu rezultatul (similar cu rezultatele de căutare)
            address = result.get('formatted_address', '')
            rating = result.get('rating', 0)
            total_reviews = result.get('user_ratings_total', 0)
            
            # Calculăm distanța dacă avem poziția
            distance_info = None
            origin_coords = None
            
            if self.use_my_position_for_distance.isChecked():
                coords_text = self.my_coords_entry.text().strip()
                origin_coords = parse_coordinates(coords_text)
            else:
                coords_text = self.explore_coords_entry.text().strip()
                origin_coords = parse_coordinates(coords_text)
            
            if origin_coords and loc:
                try:
                    dist_result = gmaps_client.distance_matrix(
                        origins=[f"{origin_coords[0]},{origin_coords[1]}"],
                        destinations=[f"{loc['lat']},{loc['lng']}"],
                        mode="driving",
                        language="ro"
                    )
                    
                    if dist_result['rows'][0]['elements'][0]['status'] == 'OK':
                        element = dist_result['rows'][0]['elements'][0]
                        distance_info = {
                            'driving': {
                                'distance': element['distance']['text'],
                                'duration': element['duration']['text']
                            }
                        }
                except:
                    pass
            
            # Construim place_data pentru card
            place_data = {
                'place_id': place_id,
                'name': name,
                'formatted_address': address,
                'vicinity': address,
                'rating': rating,
                'user_ratings_total': total_reviews,
                'opening_hours': result.get('opening_hours', {}),
                'types': result.get('types', []),
                'geometry': result.get('geometry', {})
            }
            
            # Salvăm în current_distance_info pentru card
            global current_distance_info
            if distance_info:
                current_distance_info[place_id] = distance_info
            
            # Creăm cardul folosind funcția existentă
            self.create_place_card(place_data, distance_info)
            self.results_layout.addStretch()
            
            log_success(f"Detalii afișate pentru POI: {name}")
            
        except Exception as e:
            log_error(f"Eroare la obținerea detaliilor POI: {e}")
            traceback.print_exc()
            self.clear_results()
            error_label = QLabel(f"❌ Nu s-au putut obține detaliile pentru acest loc")
            error_label.setStyleSheet("color: red; padding: 20px;")
            self.results_layout.addWidget(error_label)
    
    def on_waypoint_add(self, lat, lng):
        """Handler pentru adăugare punct intermediar din click dreapta pe hartă."""
        global selected_places, route_places_coords
        
        log_info(f"Adăugare waypoint la: {lat}, {lng}")
        
        # Facem reverse geocoding pentru a obține adresa
        try:
            address = reverse_geocode(lat, lng)
            
            # Generăm un place_id unic pentru waypoint
            import hashlib
            waypoint_id = f"waypoint_{hashlib.md5(f'{lat},{lng}'.encode()).hexdigest()[:12]}"
            
            # Extragem numele scurt din adresă
            name_parts = address.split(',')
            short_name = name_parts[0].strip() if name_parts else f"Punct {lat:.4f}, {lng:.4f}"
            
            # Verificăm dacă nu există deja
            if waypoint_id in selected_places:
                QMessageBox.information(self, "Info", f"Punctul '{short_name}' este deja în traseu!")
                return
            
            # Salvăm coordonatele
            route_places_coords[waypoint_id] = {'lat': lat, 'lng': lng, 'name': short_name}
            
            # Adăugăm în dicționarul de locații selectate
            selected_places[waypoint_id] = {'name': short_name, 'address': address}
            
            # Adăugăm în lista de traseu
            self.add_to_route_list(waypoint_id, short_name, address)
            
            # Actualizăm titlul tab-ului
            self.update_route_tab_title()
            
            # Schimbăm la tab-ul Traseu
            self.results_tabs.setCurrentIndex(1)
            
            log_success(f"Waypoint adăugat: {short_name}")
            
            # Afișăm marker pe hartă
            js_code = f"addWaypointMarker({lat}, {lng}, 'W');"
            self.web_view.page().runJavaScript(js_code)
            
        except Exception as e:
            log_error(f"Eroare la adăugarea waypoint: {e}")
            traceback.print_exc()
            QMessageBox.warning(self, "Eroare", f"Nu s-a putut adăuga punctul:\n{e}")
    
    def on_set_explore_from_map(self, lat, lng):
        """Handler pentru setare zonă de explorare din click dreapta pe hartă."""
        coords_text = f"{lat}, {lng}"
        self.explore_coords_entry.setText(coords_text)
        self.radio_explore.setChecked(True)
        
        # Actualizăm starea UI (activăm câmpurile pentru explorare)
        self.update_ui_states()
        
        # Actualizăm adresa și afișăm marker pe hartă
        self.update_address_and_center_map(
            self.explore_coords_entry, 
            self.explore_address_label, 
            "Zona de explorat", 
            "explore_coords"
        )
        
        log_success(f"Zonă de explorare setată: {coords_text}")
    
    def on_set_my_position_from_map(self, lat, lng):
        """Handler pentru setare poziție curentă din click dreapta pe hartă."""
        coords_text = f"{lat}, {lng}"
        
        # Setăm coordonatele
        self.my_coords_entry.setText(coords_text)
        
        # Selectăm radio button-ul "Lângă mine"
        self.radio_my_position.setChecked(True)
        
        # Actualizăm starea UI (activăm câmpurile pentru poziția mea)
        self.update_ui_states()
        
        # Forțăm activarea câmpului și butonului (pentru siguranță)
        self.my_coords_entry.setEnabled(True)
        self.my_coords_geo_btn.setEnabled(True)
        
        # Actualizăm adresa și afișăm marker pe hartă
        self.update_address_and_center_map(
            self.my_coords_entry, 
            self.my_coords_address_label, 
            "Poziția mea", 
            "my_coords"
        )
        
        log_success(f"Poziție curentă setată: {coords_text}")
    


    def fetch_details_now(self, place_id):
        try:
            d = gmaps_client.place(place_id=place_id, fields=['opening_hours', 'website'], language='ro')
            res = d.get('result', {})
            web = res.get('website', "")
            oh = res.get('opening_hours', {})
            stat = "Program necunoscut"
            if 'open_now' in oh:
                stat = "Deschis acum" if oh['open_now'] else "Închis acum"
            return web, stat
        except:
            return "", "Program necunoscut"

    def scan_hotspots(self):
        global route_places_coords, selected_places, diversity_settings, CATEGORIES_MAP
        
        sender_btn = self.sender()
        original_text = ""
        if isinstance(sender_btn, QPushButton):
            if not sender_btn.isEnabled(): return 
            original_text = sender_btn.text()
            sender_btn.setEnabled(False)
            sender_btn.setText("⏳ Scanez...")
            QApplication.processEvents()

        try:
            log_info("\n" + "="*40)
            log_info("🚀 START SCANARE (V44: Detalii Imediate + Logică Corectă)")
            log_info("="*40)
            
            self.clear_route()
            
            # Definim funcțiile auxiliare
            def get_cat(types):
                for k, v in CATEGORIES_MAP.items():
                    if any(t in types for t in v['keywords']): return k
                return 'other'
            
            def is_excluded(types):
                return any(t in ['lodging', 'parking', 'gas_station'] for t in types)

            def get_inventory():
                cnts = {k: 0 for k in CATEGORIES_MAP.keys()}
                cnts['other'] = 0
                for pid, data in selected_places.items():
                    pts = data.get('types', [])
                    if not pts:
                        f = next((x for x in all_hotspots if x['place_id'] == pid), None)
                        if f: pts = f['types']
                    c = get_cat(pts)
                    if c in cnts: cnts[c] += 1
                    else: cnts['other'] += 1
                return cnts

            # Citim inputurile
            try: min_reviews_top = int(self.min_reviews_entry.text().strip())
            except: min_reviews_top = 500
            
            search_coords = None
            mode = self.get_search_type()
            if mode == "my_position": search_coords = parse_coordinates(self.my_coords_entry.text())
            elif mode == "explore": search_coords = parse_coordinates(self.explore_coords_entry.text())
            elif mode == "saved_location":
                sel = self.location_combo.currentText()
                if sel in saved_locations: search_coords = parse_coordinates(saved_locations[sel])
            
            if not search_coords:
                QMessageBox.warning(self, "Eroare", "Nu am coordonate de start!")
                return

            try: radius_m = int(float(self.radius_entry.text().strip()) * 1000)
            except: radius_m = 1500
            
            log_info(f"📍 Centru: {search_coords} | Rază: {radius_m}m | Filtru: {min_reviews_top}+ recenzii")

            self.clear_results()
            
            poi_types = [
                'tourist_attraction', 'museum', 'church', 'place_of_worship',
                'park', 'restaurant', 'cafe', 'bar',
                'shopping_mall', 'store', 'pharmacy', 'bank', 'hospital'
            ]
            
            all_hotspots = []
            seen_ids = set()
            
            # Căutare Google Places
            for p_type in poi_types:
                try:
                    res = gmaps_client.places_nearby(location=search_coords, radius=radius_m, type=p_type, language='ro')
                    for p in res.get('results', []):
                        pid = p.get('place_id')
                        if pid in seen_ids: continue
                        revs = p.get('user_ratings_total', 0)
                        if revs < 10: continue 
                        seen_ids.add(pid)
                        loc = p.get('geometry', {}).get('location', {})
                        rating = p.get('rating', 0)
                        if rating < 3.8: continue 

                        all_hotspots.append({
                            'place_id': pid,
                            'name': p.get('name', 'N/A'),
                            'lat': loc.get('lat'),
                            'lng': loc.get('lng'),
                            'rating': rating,
                            'reviews': revs,
                            'address': p.get('vicinity', ''),
                            'types': p.get('types', [])
                        })
                        if pid and loc.get('lat'):
                            route_places_coords[pid] = {'lat': loc['lat'], 'lng': loc['lng'], 'name': p.get('name')}
                except: pass

            all_hotspots.sort(key=lambda x: x['reviews'], reverse=True)
            log_success(f"✅ Radar: {len(all_hotspots)} locuri valide.")

            total_v1 = 0
            total_v2 = 0
            total_v3 = 0

            # >>> PASUL 1: TOP GENERAL <<<
            if self.auto_add_hotspots_checkbox.isChecked():
                try: limit_v1 = int(self.auto_add_limit_entry.text().strip())
                except: limit_v1 = 15
                
                log_info(f"\n🌊 [V1] Start Val 1: Top {limit_v1}")
                count = 0
                for h in all_hotspots:
                    if count >= limit_v1: break
                    if h['reviews'] < min_reviews_top: continue
                    if h['place_id'] in selected_places: continue
                    if is_excluded(h['types']): continue
                    
                    cat = get_cat(h['types'])
                    inv = get_inventory()
                    if cat in diversity_settings and inv.get(cat, 0) >= diversity_settings[cat].get('max', 99):
                        continue

                    display_name = f"[V1] {h['name']}"
                    
                    # FETCH DETAILS (Site + Orar) ACUM
                    web, stat = self.fetch_details_now(h['place_id'])
                    
                    self.toggle_selection(h['place_id'], display_name, h['rating'], h['reviews'], stat, Qt.Checked.value, h['types'], web)
                    count += 1
                    log_success(f"   + Adăugat: {h['name']}")
                total_v1 = count

            # >>> PASUL 2: DIVERSITATE <<<
            if self.diversity_checkbox.isChecked():
                log_info("\n🌊 [V2] Start Val 2: Diversitate")
                for cat, rules in diversity_settings.items():
                    target = rules.get('min', 0)
                    if target <= 0: continue
                    curr = get_inventory().get(cat, 0)
                    needed = target - curr
                    if needed <= 0: continue
                    
                    cands = [h for h in all_hotspots if 
                             h['place_id'] not in selected_places and 
                             h['rating'] >= rules.get('min_rating', 0) and 
                             not is_excluded(h['types']) and 
                             get_cat(h['types']) == cat]
                    cands.sort(key=lambda x: x['reviews'], reverse=True)
                    
                    for h in cands[:needed]:
                        display_name = f"[V2] {h['name']}"
                        
                        # FETCH DETAILS ACUM
                        web, stat = self.fetch_details_now(h['place_id'])
                        
                        self.toggle_selection(h['place_id'], display_name, h['rating'], h['reviews'], stat, Qt.Checked.value, h['types'], web)
                        total_v2 += 1
                        log_success(f"   + Adăugat: {h['name']}")

            # >>> PASUL 3: GEOGRAFIC <<<
            if self.geo_coverage_checkbox.isChecked():
                try: limit_v3 = int(self.geo_limit_entry.text().strip())
                except: limit_v3 = 3
                try: min_dist_m = int(self.geo_dist_entry.text().strip())
                except: min_dist_m = 500 
                
                log_info(f"\n🌊 [V3] Start Val 3: Geografic")
                
                added_v3 = 0
                for h in all_hotspots:
                    if added_v3 >= limit_v3: break
                    if h['reviews'] < min_reviews_top: continue 
                    if h['place_id'] in selected_places: continue
                    if h['rating'] < 4.0: continue 
                    if is_excluded(h['types']): continue
                    
                    my_lat = h['lat']; my_lng = h['lng']
                    is_isolated = True
                    for pid, pdata in selected_places.items():
                        p_coords = route_places_coords.get(pid)
                        if p_coords:
                            d = haversine_distance(my_lat, my_lng, p_coords['lat'], p_coords['lng'])
                            if d < min_dist_m:
                                is_isolated = False; break
                    
                    if is_isolated:
                        display_name = f"[V3] {h['name']}"
                        special_types = h['types'] + ['poi_geographic']
                        
                        # FETCH DETAILS ACUM
                        web, stat = self.fetch_details_now(h['place_id'])
                        
                        self.toggle_selection(h['place_id'], display_name, h['rating'], h['reviews'], stat, Qt.Checked.value, special_types, web)
                        added_v3 += 1; total_v3 += 1
                        log_success(f"   + Adăugat [V3]: {h['name']}")

            # --- FINAL ---
            self.clear_results()
            self.results_tabs.setCurrentIndex(1) # Mergi la Tab Traseu
            
            visual_hotspots = [h for h in all_hotspots if h['reviews'] >= min_reviews_top]
            if visual_hotspots:
                js_code = f"addHotspotMarkers({json.dumps(visual_hotspots)});"
                self.web_view.page().runJavaScript(js_code)
                self.show_hotspots_checkbox.setChecked(True)
            
            # HEADER REZULTATE
            header = QLabel("🔥 Rezultate Scanare")
            header.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px; color: #2e7d32;")
            self.results_layout.addWidget(header)
            
            msg = f"Total: {total_v1 + total_v2 + total_v3}\n[V1] Top: {total_v1}\n[V2] Div: {total_v2}\n[V3] Geo: {total_v3}"
            summary = QLabel(msg)
            summary.setStyleSheet("font-size: 11pt; padding: 10px; font-family: monospace;")
            self.results_layout.addWidget(summary)
            self.results_layout.addStretch()
            
        except Exception as e:
            log_error(f"Err: {e}")
            traceback.print_exc()
        finally:
            if isinstance(sender_btn, QPushButton):
                sender_btn.setEnabled(True)
                sender_btn.setText(original_text if original_text else "🔥 Scanează și Generează")
    

    def create_hotspot_card(self, hotspot, rank):
        """Creează un card pentru un hotspot."""
        global selected_places
        
        card = QFrame()
        card.setFrameShape(QFrame.Box)
        card.setStyleSheet("""
            QFrame { 
                border: 2px solid #ff5722; 
                border-radius: 8px;
                padding: 4px; 
                margin: 4px; 
                background-color: #fff3e0;
            }
            QFrame:hover {
                border-color: #e64a19;
                background-color: #ffe0b2;
            }
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(4)
        
        # Header cu rank și nume
        header_layout = QHBoxLayout()
        
        # Rank
        rank_label = QLabel(f"#{rank}")
        rank_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #ff5722;")
        header_layout.addWidget(rank_label)
        
        # Nume
        name_label = ClickableLabel(hotspot['name'])
        name_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #333;")
        name_label.setWordWrap(True)
        if hotspot.get('lat') and hotspot.get('lng'):
            name_label.clicked.connect(
                lambda: self.update_map_image(hotspot['lat'], hotspot['lng'], hotspot['name'], None, hotspot.get('place_id'))
            )
        header_layout.addWidget(name_label, 1)
        
        # Checkbox pentru traseu
        place_id = hotspot.get('place_id')
        if place_id:
            sel_checkbox = QCheckBox()
            sel_checkbox.setStyleSheet("QCheckBox::indicator { width: 24px; height: 24px; }")
            if place_id in selected_places:
                sel_checkbox.setChecked(True)
            sel_checkbox.stateChanged.connect(
                lambda state, pid=place_id, n=hotspot['name'], r=hotspot['rating'], rc=hotspot['reviews'], t=hotspot.get('types', []): self.toggle_selection(pid, n, r, rc, 'Program necunoscut', state, t)
            )
            header_layout.addWidget(sel_checkbox)
        
        card_layout.addLayout(header_layout)
        
        # Info: rating și recenzii
        info_layout = QHBoxLayout()
        
        rating_label = QLabel(f"⭐ {hotspot['rating']}")
        rating_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #f57c00;")
        info_layout.addWidget(rating_label)
        
        reviews_label = QLabel(f"📝 {hotspot['reviews']} recenzii")
        reviews_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #1976d2;")
        info_layout.addWidget(reviews_label)
        
        info_layout.addStretch()
        card_layout.addLayout(info_layout)
        
        # Adresă
        if hotspot.get('address'):
            addr_label = QLabel(f"📍 {hotspot['address']}")
            addr_label.setStyleSheet("font-size: 10pt; color: #666;")
            addr_label.setWordWrap(True)
            card_layout.addWidget(addr_label)
        
        self.results_layout.addWidget(card)
    
    def clear_hotspots(self):
        """Curăță hotspots de pe hartă."""
        js_code = "clearHotspots();"
        self.web_view.page().runJavaScript(js_code)
        log_info("Hotspots curățate de pe hartă.")
    
    def toggle_hotspots_visibility(self, state):
        """Afișează sau ascunde hotspots pe hartă."""
        if state == Qt.Checked.value:
            js_code = "showHotspots();"
            self.web_view.page().runJavaScript(js_code)
            log_info("Hotspots afișate pe hartă.")
        else:
            js_code = "hideHotspots();"
            self.web_view.page().runJavaScript(js_code)
            log_info("Hotspots ascunse de pe hartă.")
        
    def on_map_zoom_changed(self, zoom):
        """Actualizează variabila globală când utilizatorul dă zoom pe hartă."""
        global current_zoom_level
        current_zoom_level = zoom
        # log_debug(f"Zoom sincronizat: {zoom}")

    
    # [V46] Funcție pentru restaurarea listei complete când se dă click pe tab-ul Rezultate
    def on_results_tab_clicked(self, index):
        # Index 0 este tab-ul de Rezultate
        if index == 0:
            global current_search_results, current_distance_info
            
            # Dacă avem rezultate stocate în memorie (cele 17), le redesenăm
            if current_search_results:
                log_info("[V46] Restaurare listă completă de rezultate...")
                self.clear_results()
                
                # Reconstruim lista
                for place in current_search_results:
                    self.create_place_card(place, current_distance_info)
                    
                # Re-adăugăm eventualele headere dacă a fost o scanare (Opțional, dar cardurile sunt baza)
                # Dacă lista a venit din scanare, ea conține deja tot ce trebuie.

    def closeEvent(self, event):
        self.save_state()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
