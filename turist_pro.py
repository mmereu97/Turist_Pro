import sys
import os
from dotenv import load_dotenv
import traceback
import googlemaps
import requests
import json
import webbrowser
import math

from PySide6.QtWidgets import (
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
        global ai_prompt_var, gemini_model_value
        gemini_model_value = self.model_entry.text().strip()
        ai_prompt_var = self.prompt_text.toPlainText().strip()
        log_success("Setările au fost salvate.")
        self.accept()


class RouteItemWidget(QFrame):
    """Widget personalizat robust pentru lista de traseu."""
    lockChanged = Signal(str, bool)
    
    def __init__(self, place_id, name, address, main_window, index=1, initial_color=None, parent=None):
        super().__init__(parent)
        self.place_id = place_id
        self.name = name
        self.address = address
        self.main_window = main_window
        self.index = index
        
        # Stil card: fundal alb, margine jos, puțin padding
        self.setStyleSheet("QFrame { background-color: white; border-bottom: 1px solid #e0e0e0; }")
        self.setMinimumHeight(90) # Mai înalt ca să încapă totul relaxat
        
        # Layout Principal Orizontal
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        
        # 1. Checkbox Imobilizare
        self.lock_checkbox = QCheckBox()
        self.lock_checkbox.setToolTip("Bifează pentru a fixa acest punct în ordine")
        self.lock_checkbox.setStyleSheet("QCheckBox::indicator { width: 20px; height: 20px; }")
        self.lock_checkbox.stateChanged.connect(self.on_lock_changed)
        layout.addWidget(self.lock_checkbox)
        
        # 2. Bulina cu Număr
        self.index_label = QLabel(str(index))
        self.index_label.setFixedSize(32, 32) # Mai mare
        self.index_label.setAlignment(Qt.AlignCenter)
        
        # Folosim culoarea primită sau o calculăm pe baza indexului
        if initial_color:
            self.initial_color = initial_color
            log_debug(f"[CULOARE] Widget creat pentru '{name}' - index={index}, folosește culoare salvată={self.initial_color}")
        else:
            self.initial_color = self.get_marker_color(index)
            log_debug(f"[CULOARE] Widget creat pentru '{name}' - index={index}, culoare nouă={self.initial_color}")
        
        self.update_index_style(index)
        layout.addWidget(self.index_label)
        
        # 3. Zona Text (Nume + Detalii) - Verticală
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.setContentsMargins(0, 0, 0, 0)
        
        # Numele Locației (FONT MARE)
        self.name_label = ClickableLabel(name)
        # --- MODIFICARE: Font 14pt ---
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14pt; color: #2c3e50;")
        self.name_label.setWordWrap(True)
        self.name_label.clicked.connect(self.show_on_map)
        text_layout.addWidget(self.name_label)
        
        # Detalii (Distanță/Timp)
        self.details_label = QLabel("")
        self.details_label.setStyleSheet("color: #555; font-size: 11pt; font-weight: 500;")
        self.details_label.setWordWrap(True)
        self.details_label.setVisible(False)
        text_layout.addWidget(self.details_label)
        
        layout.addLayout(text_layout, 1) # Stretch (ocupă tot spațiul liber)
        
        # 4. Butoane (Acum cu TEXT și Icoană)
        btns_layout = QVBoxLayout()
        btns_layout.setSpacing(4)
        btns_layout.setContentsMargins(0, 0, 0, 0)
        btns_layout.setAlignment(Qt.AlignTop)
        
        # Le punem unul sub altul sau într-un grid? Hai să le punem pe un rând orizontal
        # ca să fie ușor de apăsat, dar mai late.
        
        # Buton Web
        web_btn = self.create_wide_btn("🌐 Site", "#f8f9fa", "Deschide Website", self.open_website)
        
        # Buton Opinii
        ai_btn = self.create_wide_btn("🗣️ Opinii", "#e3f2fd", "Rezumat Opinii AI", lambda: self.generate_ai_summary(ai_btn))
        
        # Buton Info
        info_btn = self.create_wide_btn("📖 Wiki", "#fff3e0", "Info Istoric", lambda: self.show_history(info_btn))
        
        # Le adăugăm într-un layout orizontal de butoane
        btns_row = QHBoxLayout()
        btns_row.setSpacing(5)
        btns_row.addWidget(web_btn)
        btns_row.addWidget(ai_btn)
        btns_row.addWidget(info_btn)
        
        # Adăugăm rândul de butoane la layout-ul vertical din dreapta
        btns_layout.addLayout(btns_row)
        btns_layout.addStretch() # Împinge în sus
        
        layout.addLayout(btns_layout)

    def sizeHint(self):
        return QSize(0, 95)

    # --- MODIFICARE: Butoane late cu text ---
    def create_wide_btn(self, text, bg, tooltip, func):
        btn = QPushButton(text)
        btn.setFixedWidth(85) # Destul de lat pentru text
        btn.setFixedHeight(34) # Ușor de nimerit cu mouse-ul
        btn.setToolTip(tooltip)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 10pt;
                font-weight: bold;
                color: #444;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: #dcdcdc;
                border-color: #999;
            }}
        """)
        btn.clicked.connect(func)
        return btn

    def set_details(self, text):
        if text:
            self.details_label.setText(text)
            self.details_label.setVisible(True)
        else:
            self.details_label.setVisible(False)

    def update_index_style(self, index):
        self.index_label.setStyleSheet(f"""
            background-color: {self.initial_color};
            color: white; border-radius: 16px; font-weight: bold; font-size: 12pt;
        """)
    
    def on_lock_changed(self, state):
        """Emite semnal când se schimbă starea de blocare."""
        self.lockChanged.emit(self.place_id, state == Qt.Checked.value)
    
    def is_locked(self):
        """Returnează True dacă punctul este imobilizat."""
        return self.lock_checkbox.isChecked()
    
    def set_locked(self, locked):
        """Setează starea de blocare."""
        self.lock_checkbox.setChecked(locked)
    
    def set_lock_enabled(self, enabled):
        """Activează/dezactivează checkbox-ul de blocare."""
        self.lock_checkbox.setEnabled(enabled)
    
    def get_marker_color(self, index):
        """Returnează culoarea pentru index (aceleași culori ca în JavaScript)."""
        colors = [
            '#4285f4',  # Albastru
            '#ea4335',  # Roșu
            '#fbbc05',  # Galben
            '#34a853',  # Verde
            '#9c27b0',  # Mov
            '#ff5722',  # Portocaliu
            '#00bcd4',  # Cyan
            '#e91e63',  # Roz
            '#795548',  # Maro
            '#607d8b'   # Gri-albastru
        ]
        return colors[(index - 1) % len(colors)]
    
    def update_index(self, new_index):
        """Actualizează indexul afișat, păstrând culoarea inițială."""
        old_index = self.index
        self.index = new_index
        self.index_label.setText(str(new_index))
        log_debug(f"[CULOARE] update_index: '{self.name}' - old={old_index}, new={new_index}, using initial_color={self.initial_color}")
        # Folosim culoarea inițială salvată, nu culoarea noului index
        self.index_label.setStyleSheet(f"""
            background-color: {self.initial_color};
            color: white;
            border-radius: 12px;
            font-weight: bold;
            font-size: 10pt;
        """)
    
    def show_on_map(self):
        """Arată locația pe hartă."""
        global route_places_coords
        if self.place_id in route_places_coords:
            coords = route_places_coords[self.place_id]
            self.main_window.update_map_image(coords['lat'], coords['lng'], self.name, None, self.place_id)
        else:
            try:
                details = gmaps_client.place(place_id=self.place_id, fields=['geometry'], language='ro')
                loc = details.get('result', {}).get('geometry', {}).get('location', {})
                if loc:
                    route_places_coords[self.place_id] = {'lat': loc['lat'], 'lng': loc['lng']}
                    self.main_window.update_map_image(loc['lat'], loc['lng'], self.name, None, self.place_id)
            except Exception as e:
                log_error(f"Nu s-au putut obține coordonatele: {e}")
    
    def open_website(self):
        """Deschide website-ul locației."""
        try:
            details = gmaps_client.place(place_id=self.place_id, fields=['website'], language='ro')
            website = details.get('result', {}).get('website')
            if website:
                webbrowser.open(website)
            else:
                QMessageBox.information(self.main_window, "Info", f"'{self.name}' nu are website.")
        except Exception as e:
            log_error(f"Eroare: {e}")
    
    def generate_ai_summary(self, button):
        """Generează rezumat AI pentru recenzii."""
        button.setEnabled(False)
        button.setText("⏳")
        QApplication.processEvents()
        
        try:
            details = gmaps_client.place(place_id=self.place_id, fields=['review'], language='ro')
            reviews = details.get('result', {}).get('reviews', [])
            
            if not reviews:
                QMessageBox.information(self.main_window, "Info", "Nu există recenzii.")
            else:
                summary = get_ai_summary(reviews, self.name)
                dialog = QDialog(self.main_window)
                dialog.setWindowTitle(f"✨ Rezumat AI - {self.name}")
                dialog.resize(550, 450)
                layout = QVBoxLayout(dialog)
                text = QTextEdit()
                text.setReadOnly(True)
                text.setText(summary)
                layout.addWidget(text)
                dialog.exec()
        except Exception as e:
            log_error(f"Eroare: {e}")
        
        button.setEnabled(True)
        button.setText("🗣️")
    
    def show_history(self, button):
        """Afișează informații despre locație."""
        button.setEnabled(False)
        button.setText("⏳")
        QApplication.processEvents()
        
        try:
            details = gmaps_client.place(place_id=self.place_id, fields=['formatted_address'], language='ro')
            address = details.get('result', {}).get('formatted_address', '')
        except:
            address = ''
        
        info = get_history_info(self.name, address)
        dialog = HistoryDialog(self.name, info, self.main_window)
        dialog.exec()
        
        button.setEnabled(True)
        button.setText("📖")


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
        top_panel = QWidget()
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 10)
        
        controls_frame = QWidget()
        controls_layout = QGridLayout(controls_frame)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # Coloana stânga
        left_controls = QWidget()
        left_layout = QHBoxLayout(left_controls)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Tipul de căutare
        search_type_group = QGroupBox("Tip Căutare:")
        search_type_layout = QVBoxLayout(search_type_group)
        
        self.search_type_group = QButtonGroup(self)
        
        self.radio_my_position = QRadioButton("📍 Lângă mine")
        self.radio_my_position.setChecked(True)
        self.search_type_group.addButton(self.radio_my_position)
        search_type_layout.addWidget(self.radio_my_position)
        
        self.radio_saved_location = QRadioButton("🏠 Lângă locație salvată")
        self.search_type_group.addButton(self.radio_saved_location)
        search_type_layout.addWidget(self.radio_saved_location)
        
        self.radio_explore = QRadioButton("🗺️ Explorare zonă")
        self.search_type_group.addButton(self.radio_explore)
        search_type_layout.addWidget(self.radio_explore)
        
        self.radio_text = QRadioButton("🔍 Căutare text")
        self.search_type_group.addButton(self.radio_text)
        search_type_layout.addWidget(self.radio_text)
        
        left_layout.addWidget(search_type_group)
        
        # Controale specifice
        search_controls = QWidget()
        search_controls_layout = QVBoxLayout(search_controls)
        search_controls_layout.setContentsMargins(10, 0, 0, 0)
        
        # Controale pentru "Lângă mine"
        my_position_frame = QHBoxLayout()
        my_position_frame.addWidget(QLabel("Poziția mea curentă:"))
        self.my_coords_entry = QLineEdit()
        self.my_coords_entry.setFixedWidth(200)
        my_position_frame.addWidget(self.my_coords_entry)
        
# --- Butonul 1: Poziția mea ---
        self.my_coords_geo_btn = QPushButton("📍")
        self.my_coords_geo_btn.setFixedWidth(45) # Lățime mai mare (era 30/35)
        self.my_coords_geo_btn.setStyleSheet("""
            QPushButton {
                color: #d32f2f;
                font-size: 18px;
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 0px; /* Resetăm padding-ul pentru centrare automată */
            }
            QPushButton:hover {
                background-color: #ffebee;
                border-color: #d32f2f;
            }
        """)
        self.my_coords_geo_btn.clicked.connect(self.on_my_coords_geo_click)
        my_position_frame.addWidget(self.my_coords_geo_btn)
        my_position_frame.addStretch()
        
        search_controls_layout.addLayout(my_position_frame)
        
        self.my_coords_address_label = QLabel("")
        self.my_coords_address_label.setStyleSheet("color: #666; font-size: 10pt;")
        search_controls_layout.addWidget(self.my_coords_address_label)
        
        # Controale pentru "Lângă locație salvată"
        saved_location_frame = QHBoxLayout()
        saved_location_frame.addWidget(QLabel("Locație salvată:"))
        self.location_combo = QComboBox()
        self.location_combo.setFixedWidth(200)
        self.location_combo.currentTextChanged.connect(self.on_location_selected)
        saved_location_frame.addWidget(self.location_combo)
        saved_location_frame.addStretch()
        
        search_controls_layout.addLayout(saved_location_frame)
        
        # --- Butonul 2: Explorare zonă ---
        explore_frame = QHBoxLayout()
        explore_frame.addWidget(QLabel("Coordonate zonă:"))
        self.explore_coords_entry = QLineEdit()
        self.explore_coords_entry.setFixedWidth(200)
        explore_frame.addWidget(self.explore_coords_entry)
        
        self.explore_geo_btn = QPushButton("📍")
        self.explore_geo_btn.setFixedWidth(45) # Lățime mai mare (era 30/35)
        self.explore_geo_btn.setStyleSheet("""
            QPushButton {
                color: #d32f2f;
                font-size: 18px;
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 0px; /* Resetăm padding-ul pentru centrare automată */
            }
            QPushButton:hover {
                background-color: #ffebee;
                border-color: #d32f2f;
            }
        """)
        self.explore_geo_btn.clicked.connect(self.on_explore_geo_click)
        explore_frame.addWidget(self.explore_geo_btn)
        explore_frame.addStretch()
        
        search_controls_layout.addLayout(explore_frame)
        
        self.explore_address_label = QLabel("")
        self.explore_address_label.setStyleSheet("color: #666; font-size: 10pt;")
        search_controls_layout.addWidget(self.explore_address_label)
        
        left_layout.addWidget(search_controls)
        
        # Raza
        radius_widget = QWidget()
        radius_layout = QVBoxLayout(radius_widget)
        radius_layout.setContentsMargins(10, 0, 0, 0)
        
        radius_layout.addWidget(QLabel("Rază (km):"))
        self.radius_entry = QLineEdit()
        self.radius_entry.setFixedWidth(60)
        self.radius_entry.setText("1.5")
        radius_layout.addWidget(self.radius_entry)
        
        self.use_my_position_for_distance = QCheckBox("Distanțe de la\npoziția mea")
        self.use_my_position_for_distance.setStyleSheet("font-size: 9pt;")
        radius_layout.addWidget(self.use_my_position_for_distance)
        radius_layout.addStretch()
        
        left_layout.addWidget(radius_widget)
        
        # NOU: Controale pentru Hotspots
        hotspot_widget = QWidget()
        hotspot_layout = QVBoxLayout(hotspot_widget)
        hotspot_layout.setContentsMargins(10, 0, 0, 0)
        
        hotspot_layout.addWidget(QLabel("🔥 Zone Fierbinți:"))
        
        # Limita minimă de recenzii
        min_reviews_layout = QHBoxLayout()
        min_reviews_layout.addWidget(QLabel("Min recenzii:"))
        self.min_reviews_entry = QLineEdit()
        self.min_reviews_entry.setFixedWidth(60)
        self.min_reviews_entry.setText("500")
        self.min_reviews_entry.setToolTip("Numărul minim de recenzii pentru a fi considerat hotspot")
        min_reviews_layout.addWidget(self.min_reviews_entry)
        hotspot_layout.addLayout(min_reviews_layout)
        
        # Buton scanare hotspots
        scan_hotspots_btn = QPushButton("🔥 Scanează")
        scan_hotspots_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff5722;
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #e64a19;
            }
        """)
        scan_hotspots_btn.setToolTip("Scanează zona pentru locuri cu multe recenzii")
        scan_hotspots_btn.clicked.connect(self.scan_hotspots)
        hotspot_layout.addWidget(scan_hotspots_btn)
        
        # Checkbox pentru afișare/ascundere hotspots
        self.show_hotspots_checkbox = QCheckBox("Afișează pe hartă")
        self.show_hotspots_checkbox.setChecked(True)
        self.show_hotspots_checkbox.setStyleSheet("font-size: 9pt;")
        self.show_hotspots_checkbox.stateChanged.connect(self.toggle_hotspots_visibility)
        hotspot_layout.addWidget(self.show_hotspots_checkbox)
        
        hotspot_layout.addStretch()
        
        left_layout.addWidget(hotspot_widget)
        
        controls_layout.addWidget(left_controls, 0, 0)
        
        # Coloana dreapta
        
        # Coloana dreapta
        right_controls = QWidget()
        right_layout = QVBoxLayout(right_controls)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # Filtrare și Sortare
        filters_group = QGroupBox("Filtrare și Sortare:")
        filters_layout = QVBoxLayout(filters_group)
        
        # Sortare
        sort_frame = QHBoxLayout()
        sort_frame.addWidget(QLabel("Sortează după:"))
        
        self.sort_group = QButtonGroup(self)
        
        self.radio_relevance = QRadioButton("Relevanță")
        self.radio_relevance.setChecked(True)
        self.sort_group.addButton(self.radio_relevance)
        sort_frame.addWidget(self.radio_relevance)
        
        self.radio_rating = QRadioButton("Rating")
        self.sort_group.addButton(self.radio_rating)
        sort_frame.addWidget(self.radio_rating)
        
        self.radio_distance = QRadioButton("Distanță")
        self.sort_group.addButton(self.radio_distance)
        sort_frame.addWidget(self.radio_distance)
        
        sort_frame.addStretch()
        filters_layout.addLayout(sort_frame)
        
        # Rating minim
        rating_frame = QHBoxLayout()
        rating_frame.addWidget(QLabel("Rating minim:"))
        
        self.rating_group = QButtonGroup(self)
        
        self.radio_any = QRadioButton("Oricare")
        self.radio_any.setChecked(True)
        self.rating_group.addButton(self.radio_any)
        rating_frame.addWidget(self.radio_any)
        
        self.radio_3plus = QRadioButton("⭐3+")
        self.rating_group.addButton(self.radio_3plus)
        rating_frame.addWidget(self.radio_3plus)
        
        self.radio_4plus = QRadioButton("⭐4+")
        self.rating_group.addButton(self.radio_4plus)
        rating_frame.addWidget(self.radio_4plus)
        
        rating_frame.addStretch()
        filters_layout.addLayout(rating_frame)
        
        # Buton Settings
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.clicked.connect(self.open_settings)
        filters_layout.addWidget(settings_btn, alignment=Qt.AlignRight)
        
        right_layout.addWidget(filters_group)
        
        # Câmpul de căutare
        search_input_frame = QWidget()
        search_input_layout = QVBoxLayout(search_input_frame)
        search_input_layout.setContentsMargins(0, 5, 0, 0)
        
        self.prompt_label = QLabel("Introduceți un cuvânt cheie (ex: cafenea, farmacie):")
        search_input_layout.addWidget(self.prompt_label)
        
        search_row = QHBoxLayout()
        
        self.prompt_entry = QTextEdit()
        self.prompt_entry.setFixedHeight(50)
        self.prompt_entry.setFixedWidth(280)
        search_row.addWidget(self.prompt_entry)
        
        send_button = QPushButton("Caută Locuri")
        send_button.setFont(QFont("Segoe UI", 11, QFont.Bold))
        send_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a7bc8;
            }
            QPushButton:pressed {
                background-color: #2a6bb8;
            }
        """)
        send_button.clicked.connect(self.send_request)
        search_row.addWidget(send_button)
        
        route_btn = QPushButton("🗺️ Generează Traseu")
        route_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        route_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:pressed {
                background-color: #e65100;
            }
        """)
        route_btn.clicked.connect(self.generate_optimized_route)
        search_row.addWidget(route_btn)
        
        # Butoane pentru salvare/încărcare traseu
        save_route_btn = QPushButton("💾")
        save_route_btn.setToolTip("Salvează traseul în fișier")
        save_route_btn.setFixedSize(40, 40)
        save_route_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        save_route_btn.clicked.connect(self.save_route_to_file)
        search_row.addWidget(save_route_btn)
        
        load_route_btn = QPushButton("📂")
        load_route_btn.setToolTip("Încarcă traseu din fișier")
        load_route_btn.setFixedSize(40, 40)
        load_route_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        load_route_btn.clicked.connect(self.load_route_from_file)
        search_row.addWidget(load_route_btn)
        
        search_row.addStretch()
        search_input_layout.addLayout(search_row)
        
        # Label pentru afișarea totalului traseului
        self.route_total_label = QLabel("")
        self.route_total_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 12pt;
                font-weight: bold;
                padding: 5px;
                background-color: #fff3e0;
                border-radius: 4px;
            }
        """)
        self.route_total_label.setVisible(False)
        search_input_layout.addWidget(self.route_total_label)
        
        right_layout.addWidget(search_input_frame)
        
        controls_layout.addWidget(right_controls, 0, 1)
        
        top_layout.addWidget(controls_frame)
        main_layout.addWidget(top_panel)
        
        # Content frame cu hartă și rezultate
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
        
        set_explore_btn = QPushButton("⬇️ Setează la Explorare")
        set_explore_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        set_explore_btn.clicked.connect(self.set_map_center_as_explore)
        map_header.addWidget(set_explore_btn)
        
        map_layout.addLayout(map_header)
        
        # Controale zoom
        zoom_controls = QHBoxLayout()
        
        self.zoom_in_button = QPushButton("Zoom In (+)")
        self.zoom_in_button.setEnabled(False)
        self.zoom_in_button.clicked.connect(self.zoom_in)
        zoom_controls.addWidget(self.zoom_in_button)
        
        self.zoom_out_button = QPushButton("Zoom Out (-)")
        self.zoom_out_button.setEnabled(False)
        self.zoom_out_button.clicked.connect(self.zoom_out)
        zoom_controls.addWidget(self.zoom_out_button)
        
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
                color: #e65100;
                border: 1px solid #ffcc80;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ffe0b2;
            }
        """)
        clear_route_btn.clicked.connect(self.clear_route)
        route_buttons_layout.addWidget(clear_route_btn)
        
        route_buttons_layout.addStretch()
        route_tab_layout.addLayout(route_buttons_layout)
        
        self.results_tabs.addTab(route_tab, "🗺️ Traseu (0)")
        
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
            sel_checkbox.stateChanged.connect(lambda state, pid=place_id, n=name: self.toggle_selection(pid, n, state))
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
            dist_label = QLabel(f"  🚗 {dist_data['distance_text']} • {dist_data['driving_duration']}")
            dist_label.setStyleSheet("color: #1976d2; font-size: 15pt; font-weight: bold; border: none;")
            status_layout.addWidget(dist_label)
            
            if dist_data['walking_duration']:
                walk_label = QLabel(f"  🚶 {dist_data['walking_duration']}")
                walk_label.setStyleSheet("color: #388e3c; font-size: 15pt; font-weight: bold; border: none;")
                status_layout.addWidget(walk_label)
        
        status_layout.addStretch()
        card_layout.addLayout(status_layout)
        
        self.results_layout.addWidget(card)
    
    def toggle_selection(self, place_id, name, state):
        global selected_places
        if state == Qt.Checked.value:
            selected_places[place_id] = name
            log_info(f"Adăugat la traseu: {name}")
            # Adăugăm în lista de traseu
            self.add_to_route_list(place_id, name)
        else:
            if place_id in selected_places:
                del selected_places[place_id]
                log_info(f"Eliminat din traseu: {name}")
                # Eliminăm din lista de traseu
                self.remove_from_route_list(place_id)
        
        # Actualizăm titlul tab-ului
        self.update_route_tab_title()
    
    def add_to_route_list(self, place_id, name, address="", initial_color=None):
        """Adaugă o locație în lista de traseu cu widget personalizat."""
        index = self.route_list.count() + 1
        
        item = QListWidgetItem()
        item.setData(Qt.UserRole, place_id)
        
        # --- MODIFICARE: Trimitem 'address' și 'initial_color' către widget ---
        item_widget = RouteItemWidget(place_id, name, address, self, index, initial_color)
        item_widget.lockChanged.connect(self.on_lock_changed)
        
        item.setSizeHint(item_widget.sizeHint())
        
        self.route_list.addItem(item)
        self.route_list.setItemWidget(item, item_widget)
        
        self.update_lock_states()
        self.save_route_order()
    
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
                else:
                    name = str(data)
                    address = ""
                
                # Reconstruim rândul cu culoarea originală
                original_color = saved_colors.get(place_id)
                self.add_to_route_list(place_id, name, address, original_color)
        
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
    
    def renumber_route_items(self):
        """Renumerotează toate elementele din lista de traseu."""
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            widget = self.route_list.itemWidget(item)
            if isinstance(widget, RouteItemWidget):
                widget.update_index(i + 1)
    
    def reorder_route_list(self, new_order):
        """Reordonează lista de traseu conform ordinii optimizate, păstrând culorile."""
        global selected_places
        
        # 1. Salvăm culorile și stările de blocare
        saved_colors = {}
        saved_locks = {}
        
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            place_id = item.data(Qt.UserRole)
            widget = self.route_list.itemWidget(item)
            if widget:
                saved_colors[place_id] = getattr(widget, 'initial_color', None)
                saved_locks[place_id] = widget.is_locked()
        
        # 2. Golim lista
        self.route_list.clear()
        
        # 3. Reconstruim în noua ordine
        for place_id in new_order:
            if place_id in selected_places:
                data = selected_places[place_id]
                
                if isinstance(data, dict):
                    name = data.get('name', "Unknown")
                    address = data.get('address', "")
                else:
                    name = str(data)
                    address = ""
                
                # Adăugăm cu culoarea originală
                original_color = saved_colors.get(place_id)
                self.add_to_route_list(place_id, name, address, original_color)
                
                # Restaurăm starea de blocare
                last_row = self.route_list.count() - 1
                item = self.route_list.item(last_row)
                widget = self.route_list.itemWidget(item)
                if widget:
                    widget.set_locked(saved_locks.get(place_id, False))
        
        # 4. Actualizăm stările
        self.update_lock_states()
        self.save_route_order()
        log_info(f"Lista reordonată conform traseului optimizat: {len(new_order)} elemente")
    
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
        log_info("Traseul a fost golit.")
    
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
        button.setEnabled(False)
        button.setText("⏳...")
        QApplication.processEvents()
        
        try:
            details = gmaps_client.place(place_id=place_id, fields=['name', 'review'], language='ro')
            reviews = details.get('result', {}).get('reviews', [])
            
            if not reviews:
                QMessageBox.information(self, f"✨ Rezumat AI - {place_name}", 
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
        
        button.setEnabled(True)
        button.setText("🗣️ Opinii")
    
    def show_history_window(self, place_name, place_address, button):
        button.setEnabled(False)
        button.setText("⏳...")
        QApplication.processEvents()
        
        info = get_history_info(place_name, place_address)
        
        dialog = HistoryDialog(place_name, info, self)
        dialog.exec()
        
        button.setEnabled(True)
        button.setText("📖 Info")
    
    def generate_optimized_route(self):
        global selected_places, current_map_lat, current_map_lng, route_places_coords
        
        def get_waypoint_format(pid):
            """Convertește un place_id în format acceptat de Directions API.
            Pentru waypoints custom (care încep cu 'waypoint_') folosește coordonate.
            Pentru place_id-uri Google normale folosește place_id:xyz.
            """
            if pid.startswith('waypoint_'):
                # E un waypoint custom - folosim coordonatele
                if pid in route_places_coords:
                    coords = route_places_coords[pid]
                    return f"{coords['lat']},{coords['lng']}"
                else:
                    log_error(f"Nu am coordonate pentru waypoint: {pid}")
                    return None
            else:
                # E un place_id Google normal
                return f"place_id:{pid}"
        
        # Obținem ordinea din lista de traseu
        route_order = self.get_route_order()
        
        if len(route_order) < 2:
            QMessageBox.critical(self, "Eroare", "Selectează cel puțin 2 locuri pentru un traseu!")
            return
        
        # Obținem numărul de puncte blocate
        locked_count = self.get_locked_count()
        
        # Prima locație din listă este punctul de plecare
        first_place_id = route_order[0]
        
        # Extragem numele corect din dicționar
        first_data = selected_places.get(first_place_id, {})
        if isinstance(first_data, dict):
            first_place_name = first_data.get('name', "Start")
        else:
            first_place_name = str(first_data)
            
        source_name = first_place_name
        
        # Căutăm coordonatele primei locații
        start_coords = None
        if first_place_id in route_places_coords:
            coords = route_places_coords[first_place_id]
            start_coords = (coords['lat'], coords['lng'])
        else:
            for place in current_search_results:
                if place.get('place_id') == first_place_id:
                    loc = place.get('geometry', {}).get('location', {})
                    start_coords = (loc.get('lat'), loc.get('lng'))
                    break
        
        if not start_coords:
            # Fallback - doar pentru place_id-uri Google reale
            if not first_place_id.startswith('waypoint_'):
                try:
                    details = gmaps_client.place(place_id=first_place_id, fields=['geometry'], language='ro')
                    loc = details.get('result', {}).get('geometry', {}).get('location', {})
                    start_coords = (loc.get('lat'), loc.get('lng'))
                except Exception as e:
                    log_error(f"Nu s-au putut obține coordonatele pentru punctul de start: {e}")
                    QMessageBox.critical(self, "Eroare", "Nu s-au putut obține coordonatele pentru punctul de start!")
                    return
            else:
                log_error(f"Waypoint custom fără coordonate: {first_place_id}")
                QMessageBox.critical(self, "Eroare", "Nu s-au putut obține coordonatele pentru punctul de start!")
                return
        
        if not start_coords or not start_coords[0] or not start_coords[1]:
            QMessageBox.critical(self, "Eroare", "Coordonatele punctului de start nu sunt valide!")
            return
        
        start_point = f"{start_coords[0]},{start_coords[1]}"
        
        # Separăm punctele blocate de cele neblocate
        locked_ids = route_order[:locked_count] if locked_count > 0 else []
        unlocked_ids = route_order[locked_count:]
        
        log_info(f"Puncte blocate: {locked_count}, Puncte de optimizat: {len(unlocked_ids)}")
        
        try:
            final_order = []
            optimize = False
            
            if len(unlocked_ids) == 0:
                final_order = route_order
                optimize = False
            elif locked_count == 0:
                final_order = route_order
                optimize = True
            else:
                # Logica hibridă (blocat + optimizat)
                last_locked_id = locked_ids[-1]
                last_locked_coords = None
                
                if last_locked_id in route_places_coords:
                    coords = route_places_coords[last_locked_id]
                    last_locked_coords = f"{coords['lat']},{coords['lng']}"
                else:
                    # Fallback - doar pentru place_id-uri Google reale
                    if not last_locked_id.startswith('waypoint_'):
                        try:
                            details = gmaps_client.place(place_id=last_locked_id, fields=['geometry'], language='ro')
                            loc = details.get('result', {}).get('geometry', {}).get('location', {})
                            last_locked_coords = f"{loc['lat']},{loc['lng']}"
                        except:
                            last_locked_coords = start_point
                    else:
                        last_locked_coords = start_point
                
                if len(unlocked_ids) > 1:
                    unlocked_waypoints = []
                    for pid in unlocked_ids:
                        wp_format = get_waypoint_format(pid)
                        if wp_format:
                            unlocked_waypoints.append(wp_format)
                    
                    if len(unlocked_waypoints) != len(unlocked_ids):
                        log_error("Nu s-au putut converti toate waypoints pentru optimizare")
                        # Continuăm fără optimizare
                        final_order = route_order
                    elif not unlocked_waypoints:
                        log_error("Nu s-au putut converti waypoints pentru optimizare")
                        final_order = route_order
                    else:
                        opt_result = gmaps_client.directions(
                            origin=last_locked_coords,
                            destination=start_point,
                            waypoints=unlocked_waypoints,
                            optimize_waypoints=True,
                            mode="walking",
                            language='ro'
                        )
                        
                        if opt_result and 'waypoint_order' in opt_result[0]:
                            waypoint_order = opt_result[0]['waypoint_order']
                            optimized_unlocked = [unlocked_ids[i] for i in waypoint_order]
                            final_order = locked_ids + optimized_unlocked
                            log_info(f"Ordine optimizată pentru punctele neblocate: {waypoint_order}")
                        else:
                            final_order = route_order
                else:
                    final_order = route_order
                
                optimize = False
            
            # Construim waypoints pentru traseu final
            waypoints_ids = []
            for pid in final_order[1:]:
                wp_format = get_waypoint_format(pid)
                if wp_format:
                    waypoints_ids.append(wp_format)
            
            if len(waypoints_ids) != len(final_order) - 1:
                log_error("Nu s-au putut converti toate waypoints pentru traseul final")
                missing_count = len(final_order) - 1 - len(waypoints_ids)
                QMessageBox.critical(
                    self, 
                    "Eroare", 
                    f"Nu s-au putut obține coordonatele pentru {missing_count} puncte din traseu.\n\n"
                    "Acest lucru se poate întâmpla dacă aplicația a fost repornită și coordonatele nu au fost salvate.\n\n"
                    "Soluție: Elimină punctele problematice și adaugă-le din nou."
                )
                return
            
            log_info(f"Se calculează traseul final. START: {source_name} -> {len(waypoints_ids)} waypoints...")
            
            # Apelăm Directions API pentru traseul final
            directions_result = gmaps_client.directions(
                origin=start_point, 
                destination=start_point,
                waypoints=waypoints_ids, 
                optimize_waypoints=optimize,
                mode="walking", 
                language='ro'
            )
            
            if directions_result:
                route = directions_result[0]
                overview_polyline = route['overview_polyline']['points']
                
                # Dacă am optimizat tot, actualizăm final_order
                if optimize and 'waypoint_order' in route:
                    waypoint_order = route['waypoint_order']
                    final_order = [final_order[0]] + [final_order[i+1] for i in waypoint_order]

                # =================================================================================
                # --- MODIFICARE MAJORĂ: REORDONĂM LISTA ACUM (ÎNAINTE SĂ SCRIEM DETALIILE) ---
                # =================================================================================
                self.reorder_route_list(final_order)
                
                # Acum lista este curată și în ordinea corectă. Putem scrie pe ea.
                
                # Marcam startul in UI
                start_item = self.route_list.item(0)
                if start_item:
                    start_widget = self.route_list.itemWidget(start_item)
                    if start_widget:
                        start_widget.set_details("🏠 Punct de Plecare")

                # Construim rezumatul text ȘI actualizăm widget-urile
                summary_text = f"🏁 Traseu Calculat:\n\n"
                if locked_count > 0:
                    summary_text += f"🔒 Puncte fixate: {locked_count}\n\n"
                
                summary_text += f"1. 🏠 START: {source_name}\n"
                
                total_km = 0
                total_min = 0
                
                for i, place_id in enumerate(final_order[1:]):
                    leg = route['legs'][i]
                    
                    # Nume corect
                    p_data = selected_places.get(place_id, {})
                    place_name = p_data.get('name', f"Punct {i+2}") if isinstance(p_data, dict) else str(p_data)
                    
                    dist_text = leg['distance']['text']
                    dur_text = leg['duration']['text']
                    
                    lock_icon = "🔒 " if i + 1 < locked_count else ""
                    summary_text += f"{i+2}. {lock_icon}📍 {place_name} ({dist_text}, {dur_text})\n"
                    
                    total_km += leg['distance']['value']
                    total_min += leg['duration']['value']
                    
                    # --- UPDATE WIDGET PE LISTA DEJA REORDONATĂ ---
                    # Deoarece am apelat deja reorder_route_list, elementul de la indexul i+1
                    # corespunde exact cu place_id curent! Nu mai trebuie să căutăm.
                    list_index = i + 1
                    if list_index < self.route_list.count():
                        item = self.route_list.item(list_index)
                        w = self.route_list.itemWidget(item)
                        if w and w.place_id == place_id:
                            w.set_details(f"🚗 {dist_text} • 🕒 {dur_text} (de la punctul anterior)")
                
                last_leg = route['legs'][-1]
                summary_text += f"{len(final_order)+1}. 🏠 Întoarcere la START ({last_leg['distance']['text']})\n\n"
                
                summary_text += f"📊 Total: {total_km/1000:.1f} km • aprox {total_min//60} min"
                
                # Actualizăm label-ul cu totalul
                self.route_total_label.setText(f"📊 Traseu: {total_km/1000:.1f} km • aprox {total_min//60} min")
                self.route_total_label.setVisible(True)
                
                dialog = RouteDialog(summary_text, self)
                dialog.exec()
                
                # --- ACTUALIZARE HARTĂ INTERACTIVĂ ---
                safe_polyline = overview_polyline.replace('\\', '\\\\')
                js_code = f"drawPolyline('{safe_polyline}');"
                self.web_view.page().runJavaScript(js_code)
                
                # --- ADĂUGĂM MARKERELE PENTRU TRASEU ---
                markers_data = []
                for i, place_id in enumerate(final_order):
                    p_data = selected_places.get(place_id, {})
                    name = p_data.get('name', f"Punct {i+1}") if isinstance(p_data, dict) else str(p_data)
                    
                    # Culoare
                    initial_color = None
                    # Putem lua culoarea direct din widget acum
                    item = self.route_list.item(i)
                    widget = self.route_list.itemWidget(item)
                    if widget:
                         initial_color = getattr(widget, 'initial_color', None)

                    if place_id in route_places_coords:
                        coords = route_places_coords[place_id]
                        marker_data = {
                            'lat': coords['lat'],
                            'lng': coords['lng'],
                            'name': name,
                            'index': i + 1,
                            'place_id': place_id
                        }
                        if initial_color:
                            marker_data['color'] = initial_color
                        markers_data.append(marker_data)
                    else:
                        # Fallback - doar pentru place_id-uri Google reale
                        if not place_id.startswith('waypoint_'):
                            try:
                                details = gmaps_client.place(place_id=place_id, fields=['geometry', 'name'], language='ro')
                                loc = details.get('result', {}).get('geometry', {}).get('location', {})
                                if loc:
                                    route_places_coords[place_id] = {'lat': loc['lat'], 'lng': loc['lng'], 'name': name}
                                    marker_data = {
                                        'lat': loc['lat'],
                                        'lng': loc['lng'],
                                        'name': name,
                                        'index': i + 1,
                                        'place_id': place_id
                                    }
                                    if initial_color:
                                        marker_data['color'] = initial_color
                                    markers_data.append(marker_data)
                            except:
                                pass
                        else:
                            log_debug(f"Waypoint custom fără coordonate (marker skip): {place_id}")
                
                if markers_data:
                    markers_json = json.dumps(markers_data)
                    js_markers = f"addRouteMarkers({markers_json});"
                    self.web_view.page().runJavaScript(js_markers)
                
                log_success(f"Traseul interactiv și {len(markers_data)} markere au fost desenate pe hartă.")
                
        except Exception as e:
            log_error(f"Eroare traseu: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Eroare", f"Eroare la calcularea traseului: {e}")

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
                first_result = results[0]
                first_result_loc = first_result.get('geometry', {}).get('location', {})
                first_lat = first_result_loc.get('lat')
                first_lng = first_result_loc.get('lng')
                first_place_id = first_result.get('place_id')
                
                if first_lat and first_lng:
                    self.update_map_image(first_lat, first_lng, first_result.get('name'), 15, first_place_id)
                
                for place in results:
                    self.create_place_card(place, distance_info)
            
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
            "saved_locations": saved_locations,
            "saved_route": saved_route_data # --- NOU: Salvăm lista complexă ---
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
            title_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #e65100;")
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
    
    def scan_hotspots(self):
        """Scanează zona vizibilă pentru POI-uri cu multe recenzii (hotspots)."""
        global route_places_coords
        
        log_info("=" * 20 + " SCANARE HOTSPOTS " + "=" * 20)
        
        try:
            # Obținem limita minimă de recenzii
            min_reviews = int(self.min_reviews_entry.text().strip())
            if min_reviews < 1:
                raise ValueError("Limita trebuie să fie >= 1")
        except ValueError as e:
            QMessageBox.warning(self, "Eroare", f"Număr invalid de recenzii minime: {e}")
            return
        
        # Obținem coordonatele pentru căutare
        search_coords = None
        
        # Verificăm ce mod de căutare e selectat
        search_mode = self.get_search_type()
        
        if search_mode == "my_position":
            coords_text = self.my_coords_entry.text().strip()
            if coords_text:
                search_coords = parse_coordinates(coords_text)
        elif search_mode == "explore":
            coords_text = self.explore_coords_entry.text().strip()
            if coords_text:
                search_coords = parse_coordinates(coords_text)
        elif search_mode == "saved_location":
            selected_name = self.location_combo.currentText()
            if selected_name and selected_name in saved_locations:
                coords_text = saved_locations[selected_name]
                search_coords = parse_coordinates(coords_text)
        
        if not search_coords:
            QMessageBox.warning(self, "Eroare", "Nu sunt setate coordonate pentru căutare.\nSetează o poziție sau zonă de explorare.")
            return
        
        # Obținem raza
        try:
            radius_km = float(self.radius_entry.text().strip())
            radius_m = int(radius_km * 1000)
        except:
            radius_m = 1500
        
        log_info(f"Scanare hotspots: centru={search_coords}, rază={radius_m}m, min_recenzii={min_reviews}")
        
        # Afișăm loading
        loading_label = QLabel("🔥 Se scanează zona pentru hotspots...")
        loading_label.setStyleSheet("font-style: italic; color: #666; padding: 10px;")
        self.clear_results()
        self.results_layout.addWidget(loading_label)
        QApplication.processEvents()
        
        try:
            # Lista de tipuri de POI-uri populare
            poi_types = [
                'restaurant', 'cafe', 'bar', 'night_club',
                'tourist_attraction', 'museum', 'park',
                'shopping_mall', 'store', 'gym',
                'spa', 'beauty_salon', 'hotel'
            ]
            
            all_hotspots = []
            seen_place_ids = set()
            
            # Căutăm pentru mai multe tipuri
            for poi_type in poi_types:
                try:
                    results = gmaps_client.places_nearby(
                        location=search_coords,
                        radius=radius_m,
                        type=poi_type,
                        language='ro'
                    )
                    
                    places = results.get('results', [])
                    
                    for place in places:
                        place_id = place.get('place_id')
                        if place_id in seen_place_ids:
                            continue
                        
                        reviews_count = place.get('user_ratings_total', 0)
                        
                        if reviews_count >= min_reviews:
                            seen_place_ids.add(place_id)
                            
                            loc = place.get('geometry', {}).get('location', {})
                            
                            hotspot = {
                                'place_id': place_id,
                                'name': place.get('name', 'Necunoscut'),
                                'lat': loc.get('lat'),
                                'lng': loc.get('lng'),
                                'rating': place.get('rating', 0),
                                'reviews': reviews_count,
                                'address': place.get('vicinity', ''),
                                'types': place.get('types', [])
                            }
                            
                            all_hotspots.append(hotspot)
                            
                            # Salvăm coordonatele pentru traseu
                            if place_id and loc.get('lat') and loc.get('lng'):
                                route_places_coords[place_id] = {
                                    'lat': loc['lat'], 
                                    'lng': loc['lng'], 
                                    'name': place.get('name', '')
                                }
                    
                except Exception as e:
                    log_debug(f"Eroare la căutare {poi_type}: {e}")
                    continue
            
            # Sortăm după numărul de recenzii
            all_hotspots.sort(key=lambda x: x['reviews'], reverse=True)
            
            # Limităm la primele 100
            all_hotspots = all_hotspots[:100]
            
            log_success(f"Găsite {len(all_hotspots)} hotspots cu >= {min_reviews} recenzii")
            
            # Afișăm pe hartă
            if all_hotspots:
                markers_json = json.dumps(all_hotspots)
                js_code = f"addHotspotMarkers({markers_json});"
                self.web_view.page().runJavaScript(js_code)
                # Bifăm checkbox-ul pentru a arăta că sunt afișate
                self.show_hotspots_checkbox.setChecked(True)
            
            # Afișăm rezultatele în panoul de rezultate
            self.clear_results()
            
            if not all_hotspots:
                no_results = QLabel(f"❌ Nu s-au găsit locuri cu >= {min_reviews} recenzii în această zonă.")
                no_results.setStyleSheet("color: #666; padding: 20px;")
                self.results_layout.addWidget(no_results)
            else:
                # Header
                header = QLabel(f"🔥 {len(all_hotspots)} Hotspots (>= {min_reviews} recenzii)")
                header.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px; color: #ff5722;")
                self.results_layout.addWidget(header)
                
                # Afișăm top 20 în listă
                for i, hotspot in enumerate(all_hotspots[:20]):
                    self.create_hotspot_card(hotspot, i + 1)
                
                if len(all_hotspots) > 20:
                    more_label = QLabel(f"... și încă {len(all_hotspots) - 20} hotspots pe hartă")
                    more_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
                    self.results_layout.addWidget(more_label)
            
            self.results_layout.addStretch()
            
        except Exception as e:
            log_error(f"Eroare la scanarea hotspots: {e}")
            traceback.print_exc()
            self.clear_results()
            error_label = QLabel(f"❌ Eroare la scanare: {e}")
            error_label.setStyleSheet("color: red; padding: 20px;")
            self.results_layout.addWidget(error_label)
    
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
                lambda state, pid=place_id, n=hotspot['name']: self.toggle_selection(pid, n, state)
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
