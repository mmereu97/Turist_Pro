import sys
import os
import shutil
import datetime
import re
from dotenv import load_dotenv
import traceback
import googlemaps
import requests
import json
import webbrowser
import math

# --- IMPORT MANAGER DATE CUSTOM ---
try:
    from custom_data_manager import CustomDataManager
except ImportError:
    print("EROARE CRITICĂ: Lipsește fișierul 'custom_data_manager.py'!")

# --- VARIABILE GLOBALE LOGARE ---
current_log_filename = None  

class Colors:
    OKGREEN = '\033[92m'
    FAIL = '\033[91m'
    WARNING = '\033[93m'
    OKBLUE = '\033[94m'
    HEADER = '\033[95m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'

def strip_ansi_codes(text):
    """Curăță culorile pentru fișierul text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def write_to_file(message, tag="INFO"):
    """Funcția supremă de scriere: Deschide -> Scrie -> Închide."""
    global current_log_filename
    if current_log_filename:
        try:
            clean_msg = strip_ansi_codes(str(message))
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            with open(current_log_filename, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{tag}] {clean_msg}\n")
        except Exception as e:
            print(f"Log Error: {e}")

# --- FUNCȚIILE DE LOGARE (Unicele și Adevăratele) ---

def log_debug(message, color=Colors.OKBLUE):
    print(f"{color}[DEBUG] {message}{Colors.ENDC}")
    write_to_file(message, "DEBUG")

def log_success(message):
    print(f"{Colors.OKGREEN}{Colors.BOLD}[SUCCESS] {message}{Colors.ENDC}")
    write_to_file(message, "SUCCESS")

def log_error(message):
    print(f"{Colors.FAIL}{Colors.BOLD}[ERROR] {message}{Colors.ENDC}")
    write_to_file(message, "ERROR")

def log_warning(message):
    print(f"{Colors.WARNING}[WARNING] {message}{Colors.ENDC}")
    write_to_file(message, "WARNING")

def log_info(message):
    print(f"{Colors.HEADER}[INFO] {message}{Colors.ENDC}")
    write_to_file(message, "INFO")

# --- [NOU] FUNCȚIE PENTRU DETALII MASSIVE (DOAR ÎN FIȘIER) ---
def log_file_only(message, tag="DATA"):
    """Scrie doar în fișierul text, NU afișează în consolă."""
    write_to_file(message, tag)


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

def decode_polyline(polyline_str):
    """Decodifică string-ul polyline de la Google într-o listă de (lat, lng)."""
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {'latitude': 0, 'longitude': 0}
    while index < len(polyline_str):
        for unit in ['latitude', 'longitude']: 
            shift, result = 0, 0
            while True:
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1f) << shift
                shift += 5
                if not byte >= 0x20:
                    break
            if (result & 1):
                changes[unit] = ~(result >> 1)
            else:
                changes[unit] = (result >> 1)
        lat += changes['latitude']
        lng += changes['longitude']
        coordinates.append((lat / 100000.0, lng / 100000.0))
    return coordinates

def point_line_distance(point, start, end):
    """
    Calculează distanța minimă (în metri) de la punctul 'point' 
    la segmentul de linie definit de 'start' și 'end'.
    """
    lat0, lon0 = math.radians(point[0]), math.radians(point[1])
    lat1, lon1 = math.radians(start[0]), math.radians(start[1])
    lat2, lon2 = math.radians(end[0]), math.radians(end[1])

    if lat1 == lat2 and lon1 == lon2:
        return haversine_distance(point[0], point[1], start[0], start[1])

    # Convertim în cartezian aprox pentru calcul rapid de proiecție
    x = (lon0 - lon1) * math.cos((lat0 + lat1) / 2)
    y = lat0 - lat1
    dx = (lon2 - lon1) * math.cos((lat2 + lat1) / 2)
    dy = lat2 - lat1
    
    dot = x * dx + y * dy
    len_sq = dx * dx + dy * dy
    param = -1
    if len_sq != 0:
        param = dot / len_sq

    if param < 0:
        xx, yy = lon1, lat1
    elif param > 1:
        xx, yy = lon2, lat2
    else:
        xx = lon1 + param * dx
        yy = lat1 + param * dy

    # Înapoi la distanța haversine
    # Aproximativ: distanța dintre (lat0, lon0) și punctul proiectat
    # Pentru precizie maximă folosim haversine între Point și Proiecție
    # (Proiecția în radiani trebuie convertită la grade aprox)
    proj_lat = math.degrees(yy)
    proj_lon = math.degrees(xx) / math.cos((lat0+yy)/2) # Corecție long
    # Simplificare: calculăm distanța direct folosind formula Cross-Track pentru sferă e prea complex
    # Folosim implementarea Haversine directă între pct și proiecția pe segment
    return haversine_distance(point[0], point[1], math.degrees(lat1 + param*dy), math.degrees(lon1 + param*dx))


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
custom_manager = CustomDataManager()

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

# Variabile globale
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

# --- SISTEM MEMORIE DUBLĂ (CIRCULAR vs LINIAR) ---
selected_places = {}        # Memorie pentru Traseu CIRCULAR (City Break)
route_places_coords = {}    # Coordonate pentru Circular

linear_places = {}          # Memorie pentru Traseu LINIAR (A -> B)
linear_places_coords = {}   # Coordonate pentru Liniar

is_linear_mode = False      # Flag: False = Circular, True = Liniar (A->B)
# -------------------------------------------------

place_initial_colors = {}
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
    Gestionează automat limitele API (MAX_DIMENSIONS_EXCEEDED) prin spargerea în loturi (chunks).
    """
    if not origin_coords or not destinations:
        return {}
    
    try:
        origin_str = f"{origin_coords[0]},{origin_coords[1]}"
        all_dest_coords = []
        all_place_ids = []
        
        # 1. Pregătim listele brute
        for dest in destinations:
            loc = dest.get('geometry', {}).get('location', {})
            if loc.get('lat') and loc.get('lng'):
                all_dest_coords.append(f"{loc['lat']},{loc['lng']}")
                all_place_ids.append(dest.get('place_id'))
        
        if not all_dest_coords:
            return {}

        # 2. Spargem în loturi de maxim 25 (Limita Google Distance Matrix)
        CHUNK_SIZE = 25
        final_distance_info = {}
        
        # Iterăm prin bucăți
        for i in range(0, len(all_dest_coords), CHUNK_SIZE):
            chunk_coords = all_dest_coords[i : i + CHUNK_SIZE]
            chunk_ids = all_place_ids[i : i + CHUNK_SIZE]
            
            log_info(f"Distance Matrix: Procesez lotul {i//CHUNK_SIZE + 1} ({len(chunk_coords)} destinații)...")
            
            # Apel Driving
            driving_result = gmaps_client.distance_matrix(
                origins=[origin_str],
                destinations=chunk_coords,
                mode="driving",
                language="ro"
            )
            
            # Apel Walking (doar dacă sunt puține, sau opțional - aici îl lăsăm)
            walking_result = gmaps_client.distance_matrix(
                origins=[origin_str],
                destinations=chunk_coords,
                mode="walking",
                language="ro"
            )
            
            # Procesăm rezultatele acestui lot
            drv_rows = driving_result.get('rows', [{}])[0].get('elements', [])
            wlk_rows = walking_result.get('rows', [{}])[0].get('elements', [])
            
            for idx, place_id in enumerate(chunk_ids):
                if idx < len(drv_rows):
                    d_elem = drv_rows[idx]
                    w_elem = wlk_rows[idx] if idx < len(wlk_rows) else {}
                    
                    dist_text = 'N/A'
                    dur_text = 'N/A'
                    dist_km = 9999
                    walk_dur = None
                    
                    if d_elem.get('status') == 'OK':
                        dist_text = d_elem.get('distance', {}).get('text', 'N/A')
                        dur_text = d_elem.get('duration', {}).get('text', 'N/A')
                        dist_val = d_elem.get('distance', {}).get('value', 0)
                        dist_km = dist_val / 1000
                    
                    if w_elem.get('status') == 'OK':
                        walk_dur = w_elem.get('duration', {}).get('text')
                    
                    final_distance_info[place_id] = {
                        'distance_text': dist_text,
                        'driving_duration': dur_text,
                        'distance_km': dist_km,
                        'walking_duration': walk_dur
                    }

        log_success(f"Distance Matrix: Finalizat pentru {len(final_distance_info)} locuri.")
        return final_distance_info
        
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

        # --- BLOC NOU START ---
        # Tab 4: Date Custom
        custom_tab = QWidget()
        custom_layout = QVBoxLayout(custom_tab)
        
        self.cb_custom_enable = QCheckBox("Activează 'Date Custom' (Mănăstiri)")
        self.cb_custom_enable.setChecked(custom_manager.is_enabled)
        custom_layout.addWidget(self.cb_custom_enable)
        
        h_file = QHBoxLayout()
        self.custom_path_entry = QLineEdit(custom_manager.file_path)
        h_file.addWidget(self.custom_path_entry)
        btn_browse = QPushButton("📂")
        btn_browse.clicked.connect(self.browse_custom_file) # Vom crea metoda asta
        h_file.addWidget(btn_browse)
        custom_layout.addLayout(h_file)
        
        btn_load = QPushButton("Încarcă Datele Acum")
        btn_load.clicked.connect(self.load_custom_data_action) # Vom crea metoda asta
        custom_layout.addWidget(btn_load)
        custom_layout.addStretch()
        
        self.notebook.addTab(custom_tab, "✞ Date Custom")
        # --- BLOC NOU FINAL ---

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


    def browse_custom_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Selectează Excel", "", "Excel (*.xlsx)")
        if f: self.custom_path_entry.setText(f)

    def load_custom_data_action(self):
        path = self.custom_path_entry.text()
        if not path: return
        cnt = custom_manager.load_from_excel(path)
        QMessageBox.information(self, "Info", f"S-au încărcat {cnt} mănăstiri.")
        if cnt > 0: custom_manager.is_enabled = True

    
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
            


        custom_manager.is_enabled = self.cb_custom_enable.isChecked()
        if custom_manager.is_enabled:
            custom_manager.load_from_excel(self.custom_path_entry.text())

        log_success("Setările au fost salvate.")
        self.accept()



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
        self.setWindowTitle("City Break Assistant (PySide6)")
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
        
# --- GRUP 1: CONFIGURARE ZONĂ (V59 - LĂȚIME 300 RESTAURATĂ) ---
        g1 = QGroupBox("1. Configurare Zonă")
        g1.setFixedWidth(460)
        l1 = QVBoxLayout(g1)
        l1.setSpacing(4)
        
        # 1. RADIO BUTTONS
        gr = QGridLayout()
        gr.setContentsMargins(0, 0, 0, 0)
        self.search_type_group = QButtonGroup(self)
        
        self.radio_my_position = QRadioButton("Lângă mine"); self.radio_my_position.setChecked(True); self.search_type_group.addButton(self.radio_my_position); gr.addWidget(self.radio_my_position, 0, 0)
        self.radio_explore = QRadioButton("Explorare"); self.search_type_group.addButton(self.radio_explore); gr.addWidget(self.radio_explore, 0, 1)
        self.radio_saved_location = QRadioButton("Salvat"); self.search_type_group.addButton(self.radio_saved_location); gr.addWidget(self.radio_saved_location, 0, 2)
        self.radio_text = QRadioButton("Text"); self.search_type_group.addButton(self.radio_text); gr.addWidget(self.radio_text, 1, 0)
        self.radio_route_mode = QRadioButton("Traseu A->B"); self.search_type_group.addButton(self.radio_route_mode); gr.addWidget(self.radio_route_mode, 1, 1, 1, 2)
        
        l1.addLayout(gr)
        
        # --- CONSTANTE DE STIL ---
        INPUT_H = 32       
        BTN_WIDTH = 90     
        COORD_WIDTH = 300  # <--- RESTAURAT LA 300
        BTN_STYLE = "padding: 0px;" 
        
        # --- CONTAINER: LÂNGĂ MINE ---
        self.c_my = QWidget(); l_my = QVBoxLayout(self.c_my); l_my.setContentsMargins(0,0,0,0); l_my.setSpacing(2)
        h_my = QHBoxLayout(); 
        
        h_my.addWidget(QLabel("Coord:")) 
        
        self.my_coords_entry = QLineEdit()
        self.my_coords_entry.setFixedHeight(INPUT_H)
        self.my_coords_entry.setFixedWidth(COORD_WIDTH)
        h_my.addWidget(self.my_coords_entry)
        
        self.my_coords_geo_btn = QPushButton("📍 Arată")
        self.my_coords_geo_btn.setFixedSize(BTN_WIDTH, INPUT_H)
        self.my_coords_geo_btn.setStyleSheet(BTN_STYLE)
        self.my_coords_geo_btn.clicked.connect(self.on_my_coords_geo_click)
        h_my.addWidget(self.my_coords_geo_btn)
        
        h_my.addStretch() 
        l_my.addLayout(h_my)
        self.my_coords_address_label = QLabel(""); self.my_coords_address_label.setStyleSheet("color: #666; font-size: 8pt;")
        l_my.addWidget(self.my_coords_address_label)
        l1.addWidget(self.c_my)
        
        # --- CONTAINER: EXPLORARE ---
        self.c_exp = QWidget(); l_exp = QVBoxLayout(self.c_exp); l_exp.setContentsMargins(0,0,0,0); l_exp.setSpacing(2)
        h_exp = QHBoxLayout(); 
        
        h_exp.addWidget(QLabel("Coord:")) 
        
        self.explore_coords_entry = QLineEdit()
        self.explore_coords_entry.setPlaceholderText("Click pe hartă")
        self.explore_coords_entry.setFixedHeight(INPUT_H)
        self.explore_coords_entry.setFixedWidth(COORD_WIDTH)
        h_exp.addWidget(self.explore_coords_entry)
        
        self.explore_geo_btn = QPushButton("📍 Arată")
        self.explore_geo_btn.setFixedSize(BTN_WIDTH, INPUT_H)
        self.explore_geo_btn.setStyleSheet(BTN_STYLE)
        self.explore_geo_btn.clicked.connect(self.on_explore_geo_click)
        h_exp.addWidget(self.explore_geo_btn)
        
        h_exp.addStretch()
        l_exp.addLayout(h_exp)
        self.explore_address_label = QLabel(""); self.explore_address_label.setStyleSheet("color: #666; font-size: 8pt;")
        l_exp.addWidget(self.explore_address_label)
        l1.addWidget(self.c_exp)
        
        # --- CONTAINER: SALVAT ---
        self.c_sav = QWidget(); l_sav = QVBoxLayout(self.c_sav); l_sav.setContentsMargins(0,0,0,0); l_sav.setSpacing(2)
        
        self.location_combo = QComboBox()
        self.location_combo.setFixedHeight(INPUT_H)
        self.location_combo.currentTextChanged.connect(self.on_location_selected)
        l_sav.addWidget(self.location_combo)
        
        h_sav_coords = QHBoxLayout()
        
        h_sav_coords.addWidget(QLabel("Coord:"))
        
        self.saved_coords_entry = QLineEdit()
        self.saved_coords_entry.setPlaceholderText("Coordonate...")
        self.saved_coords_entry.setFixedHeight(INPUT_H)
        self.saved_coords_entry.setFixedWidth(COORD_WIDTH)
        h_sav_coords.addWidget(self.saved_coords_entry)
        
        self.saved_geo_btn = QPushButton("📍 Arată")
        self.saved_geo_btn.setFixedSize(BTN_WIDTH, INPUT_H)
        self.saved_geo_btn.setStyleSheet(BTN_STYLE)
        self.saved_geo_btn.clicked.connect(lambda: self.update_address_and_center_map(self.saved_coords_entry, self.saved_address_label, "Locație Salvată", "saved"))
        h_sav_coords.addWidget(self.saved_geo_btn)
        
        h_sav_coords.addStretch()
        l_sav.addLayout(h_sav_coords)
        self.saved_address_label = QLabel(""); self.saved_address_label.setStyleSheet("color: #666; font-size: 8pt;")
        l_sav.addWidget(self.saved_address_label)
        l1.addWidget(self.c_sav)




        # ### CONTAINER TRASEU A->B ###
        self.c_route = QWidget(); l_route = QVBoxLayout(self.c_route); l_route.setContentsMargins(0,0,0,0)
        l_route.setSpacing(2)
        
        # --- Linia A (Start) ---
        row_a = QHBoxLayout()
        lbl_a = QLabel("Pornire (A):"); lbl_a.setFixedWidth(75)
        row_a.addWidget(lbl_a)
        
        self.route_start_entry = QLineEdit()
        self.route_start_entry.setPlaceholderText("Coordonate start...")
        self.route_start_entry.setFixedHeight(INPUT_H)
        row_a.addWidget(self.route_start_entry)
        
        # Buton mic "Acadea"
        self.btn_show_start = QPushButton("📍")
        self.btn_show_start.setFixedSize(30, INPUT_H) # Pătrat mic
        self.btn_show_start.setStyleSheet("padding: 0px; font-size: 12pt;")
        self.btn_show_start.setToolTip("Arată Punctul A pe Hartă")
        # Conectăm la funcția de centrare hartă (folosim lbl_a ca dummy pentru label)
        self.btn_show_start.clicked.connect(lambda: self.update_address_and_center_map(self.route_start_entry, self.route_start_lbl, "Start Traseu"))
        row_a.addWidget(self.btn_show_start)
        
        l_route.addLayout(row_a)
        
        # Adresa A
        self.route_start_lbl = QLabel("..."); self.route_start_lbl.setStyleSheet("color: #666; font-size: 8pt; margin-left: 80px;")
        l_route.addWidget(self.route_start_lbl)
        
        # --- Linia B (Destinație) ---
        row_b = QHBoxLayout()
        lbl_b = QLabel("Dest. (B):"); lbl_b.setFixedWidth(75)
        row_b.addWidget(lbl_b)
        
        self.route_end_entry = QLineEdit()
        self.route_end_entry.setPlaceholderText("Coordonate sosire...")
        self.route_end_entry.setFixedHeight(INPUT_H)
        row_b.addWidget(self.route_end_entry)
        
        # Buton mic "Acadea"
        self.btn_show_end = QPushButton("📍")
        self.btn_show_end.setFixedSize(30, INPUT_H)
        self.btn_show_end.setStyleSheet("padding: 0px; font-size: 12pt;")
        self.btn_show_end.setToolTip("Arată Punctul B pe Hartă")
        self.btn_show_end.clicked.connect(lambda: self.update_address_and_center_map(self.route_end_entry, self.route_end_lbl, "Destinație Traseu"))
        row_b.addWidget(self.btn_show_end)
        
        l_route.addLayout(row_b)
        
        # Adresa B
        self.route_end_lbl = QLabel("..."); self.route_end_lbl.setStyleSheet("color: #666; font-size: 8pt; margin-left: 80px;")
        l_route.addWidget(self.route_end_lbl)
        
        # Buton Calcul
        self.btn_calc_simple = QPushButton("🚗 Calculează Traseu Rapid")
        self.btn_calc_simple.setFixedHeight(36)
        self.btn_calc_simple.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; border-radius: 4px;")
        self.btn_calc_simple.clicked.connect(self.calculate_simple_driving_route)
        l_route.addWidget(self.btn_calc_simple)
        
        l1.addWidget(self.c_route)




        
        # --- RAZĂ ---
        self.c_rad = QWidget(); l_rad = QHBoxLayout(self.c_rad); l_rad.setContentsMargins(0,2,0,0)
        l_rad.addWidget(QLabel("Rază (km):"))
        self.radius_entry = QLineEdit("1.5"); self.radius_entry.setFixedSize(40, INPUT_H); self.radius_entry.setAlignment(Qt.AlignCenter)
        l_rad.addWidget(self.radius_entry)
        self.use_my_position_for_distance = QCheckBox("Dist. de la mine"); l_rad.addWidget(self.use_my_position_for_distance)
        l_rad.addStretch() 
        l1.addWidget(self.c_rad)
        
        l1.addStretch()
        
        # Buton Setare Explorare
        self.btn_set_exp = QPushButton("⬇️ Setează Explorare Aici")
        self.btn_set_exp.setFixedHeight(45)
        self.btn_set_exp.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold; font-size: 12pt; border-radius: 5px;")
        self.btn_set_exp.clicked.connect(self.set_map_center_as_explore)
        l1.addWidget(self.btn_set_exp)
        
        def update_vis():
            is_route = self.radio_route_mode.isChecked()
            
            # 1. Schimbăm modul de memorie
            self.switch_route_mode(to_linear=is_route)

            # 2. Gestionăm containerele de sus (Grupul 1)
            self.c_my.setVisible(self.radio_my_position.isChecked())
            self.c_exp.setVisible(self.radio_explore.isChecked())
            self.btn_set_exp.setVisible(not self.radio_text.isChecked() and not is_route)
            self.c_sav.setVisible(self.radio_saved_location.isChecked())
            self.c_route.setVisible(is_route)
            self.c_rad.setVisible(not self.radio_text.isChecked() and not is_route)
            
            # 3. Auto-fill pentru Traseu A->B
            if is_route:
                if not self.route_start_entry.text():
                    self.route_start_entry.setText(self.my_coords_entry.text())
                    self.update_address_from_coords(self.route_start_entry, self.route_start_lbl)
                if not self.route_end_entry.text():
                    exp = self.explore_coords_entry.text()
                    sav = self.saved_coords_entry.text()
                    if exp: self.route_end_entry.setText(exp)
                    elif sav: self.route_end_entry.setText(sav)
                    if self.route_end_entry.text():
                        self.update_address_from_coords(self.route_end_entry, self.route_end_lbl)

            # 4. MANAGEMENT VIZIBILITATE GRUP 2
            is_circular = not is_route
            
            # A. Elemente Exclusive Circular
            # Ascundem bifa Google și tot containerul cu V1/V2/V3
            self.show_hotspots_checkbox.setVisible(is_circular)
            self.container_circular_opts.setVisible(is_circular)
            
            # B. Elemente Exclusive Liniar
            # Arătăm laboratorul de parametri (Pas, Rază, Abatere Google)
            self.container_linear_opts.setVisible(is_route)
            
            # C. Elemente Mixte (Abaterea Custom)
            # Acestea sunt pe rândul cu bifa Custom, dar apar doar la Liniar
            self.lbl_cust_dev.setVisible(is_route)
            self.custom_deviation_entry.setVisible(is_route)
            self.lbl_cust_km.setVisible(is_route)
            
            # Notă: Bifa Custom și Butonul Scanare rămân vizibile mereu

        self.search_type_group.buttonClicked.connect(update_vis)
        QTimer.singleShot(10, update_vis)
        
        top_layout.addWidget(g1)



        
        # --- GRUP 2: GENERATOR INTELIGENT (V62 - LABORATOR TRASEU) ---
        g2 = QGroupBox("2. Generator Inteligent")
        g2.setFixedWidth(460) 
        l2 = QVBoxLayout(g2)
        l2.setSpacing(6)
        
        # ============================================================
        # ZONA A: COMUNĂ / CIRCULARĂ
        # ============================================================
        
        # 1. Checkbox Google (Vizibil doar la Circular)
        self.show_hotspots_checkbox = QCheckBox("Arată zonele interesante pe hartă (Google)", self)
        self.show_hotspots_checkbox.setStyleSheet("font-size: 10pt;")
        self.show_hotspots_checkbox.setChecked(True)
        self.show_hotspots_checkbox.stateChanged.connect(self.toggle_hotspots_visibility)
        l2.addWidget(self.show_hotspots_checkbox)

        # 2. Checkbox Custom (Vizibil MEREU)
        # Acum punem și abaterea Custom pe același rând
        h_cust = QHBoxLayout()
        self.show_custom_checkbox = QCheckBox("Arată Strat Custom", self)
        self.show_custom_checkbox.setStyleSheet("color: #8e24aa; font-weight: bold; font-size: 10pt;")
        self.show_custom_checkbox.setChecked(True)
        self.show_custom_checkbox.stateChanged.connect(self.toggle_custom_layer)
        h_cust.addWidget(self.show_custom_checkbox)
        
        h_cust.addStretch()
        
        # Input Abatere Custom (Vizibil doar la Liniar - gestionat din update_vis)
        self.lbl_cust_dev = QLabel("Abatere:")
        h_cust.addWidget(self.lbl_cust_dev)
        self.custom_deviation_entry = QLineEdit("5", self) # Default 5 km
        self.custom_deviation_entry.setFixedSize(30, 26)
        self.custom_deviation_entry.setAlignment(Qt.AlignCenter)
        h_cust.addWidget(self.custom_deviation_entry)
        self.lbl_cust_km = QLabel("km")
        h_cust.addWidget(self.lbl_cust_km)
        
        l2.addLayout(h_cust)
        
        self.line_separator = QFrame(); self.line_separator.setFrameShape(QFrame.HLine); self.line_separator.setStyleSheet("color: #ddd;")
        l2.addWidget(self.line_separator)
        
        STYLE_V_TITLE = "font-weight: bold; font-size: 11pt;"
        INPUT_H = 30
        
        # ============================================================
        # ZONA B: ELEMENTE EXCLUSIVE CIRCULAR (V1, V2, V3)
        # ============================================================
        self.container_circular_opts = QWidget()
        l_circ = QVBoxLayout(self.container_circular_opts)
        l_circ.setContentsMargins(0,0,0,0)
        
        # V1
        h_v1 = QHBoxLayout()
        self.auto_add_hotspots_checkbox = QCheckBox("[V1] Top", self)
        self.auto_add_hotspots_checkbox.setStyleSheet(f"color: #1565c0; {STYLE_V_TITLE}")
        h_v1.addWidget(self.auto_add_hotspots_checkbox)
        h_v1.addStretch()
        self.lbl_lim_max = QLabel("Limită Maximă:")
        h_v1.addWidget(self.lbl_lim_max)
        self.auto_add_limit_entry = QLineEdit("15", self)
        self.auto_add_limit_entry.setFixedSize(40, INPUT_H); self.auto_add_limit_entry.setAlignment(Qt.AlignCenter)
        h_v1.addWidget(self.auto_add_limit_entry)
        self.lbl_min_rev = QLabel("Nr. Minim Reviews:")
        h_v1.addWidget(self.lbl_min_rev)
        self.min_reviews_entry = QLineEdit("500", self) 
        self.min_reviews_entry.setFixedSize(60, INPUT_H); self.min_reviews_entry.setAlignment(Qt.AlignCenter)
        h_v1.addWidget(self.min_reviews_entry)
        l_circ.addLayout(h_v1)
        
        # V2
        h_v2 = QHBoxLayout()
        self.diversity_checkbox = QCheckBox("[V2] Diversitate", self)
        self.diversity_checkbox.setStyleSheet(f"color: #2e7d32; {STYLE_V_TITLE}")
        h_v2.addWidget(self.diversity_checkbox)
        h_v2.addStretch()
        b_div = QPushButton("⚙️ Setări", self)
        b_div.setFixedSize(120, 35); b_div.clicked.connect(lambda: self.open_settings())
        h_v2.addWidget(b_div)
        l_circ.addLayout(h_v2)
        
        # V3
        h_v3 = QHBoxLayout()
        self.geo_coverage_checkbox = QCheckBox("[V3] Popular (3.0 - 4.0⭐)", self) 
        self.geo_coverage_checkbox.setStyleSheet(f"color: #e65100; {STYLE_V_TITLE}")
        h_v3.addWidget(self.geo_coverage_checkbox)
        h_v3.addStretch()
        self.lbl_nr_loc = QLabel("Nr. Locuri:")
        h_v3.addWidget(self.lbl_nr_loc)
        self.geo_limit_entry = QLineEdit("3", self)
        self.geo_limit_entry.setFixedSize(35, INPUT_H); self.geo_limit_entry.setAlignment(Qt.AlignCenter)
        h_v3.addWidget(self.geo_limit_entry)
        l_circ.addLayout(h_v3)
        
        l2.addWidget(self.container_circular_opts)

        # ============================================================
        # ZONA C: ELEMENTE EXCLUSIVE LINIAR (LABORATOR TRASEU)
        # ============================================================
        self.container_linear_opts = QWidget()
        l_lin = QVBoxLayout(self.container_linear_opts)
        l_lin.setContentsMargins(0, 0, 0, 0)
        l_lin.setSpacing(8) # Spațiu între rânduri
        
        # Rând 1: Cuvinte Cheie
        l_lin.addWidget(QLabel("<b>Ce căutăm?</b> (Google Keywords):"))
        self.route_keywords_entry = QLineEdit("benzinarie, restaurant, parcare", self)
        self.route_keywords_entry.setPlaceholderText("ex: Socar, McDonalds, Castel")
        self.route_keywords_entry.setFixedHeight(32)
        l_lin.addWidget(self.route_keywords_entry)
        
        # Rând 2: Pas și Rază
        h_lab1 = QHBoxLayout()
        
        h_lab1.addWidget(QLabel("Pas scanare:"))
        self.scan_step_entry = QLineEdit("10", self)
        self.scan_step_entry.setFixedSize(40, 30)
        self.scan_step_entry.setAlignment(Qt.AlignCenter)
        h_lab1.addWidget(self.scan_step_entry)
        h_lab1.addWidget(QLabel("km"))
        
        h_lab1.addSpacing(20) # Spațiu mare între grupuri
        
        h_lab1.addWidget(QLabel("Rază cerc:"))
        self.scan_radius_entry = QLineEdit("7", self)
        self.scan_radius_entry.setFixedSize(40, 30)
        self.scan_radius_entry.setAlignment(Qt.AlignCenter)
        h_lab1.addWidget(self.scan_radius_entry)
        h_lab1.addWidget(QLabel("km"))
        
        h_lab1.addStretch()
        l_lin.addLayout(h_lab1)

        # Rând 3: Abatere Google
        h_lab2 = QHBoxLayout()
        h_lab2.addWidget(QLabel("<b>Abatere Max (Google):</b>"))
        self.google_deviation_entry = QLineEdit("100", self)
        self.google_deviation_entry.setFixedSize(50, 30)
        self.google_deviation_entry.setAlignment(Qt.AlignCenter)
        self.google_deviation_entry.setStyleSheet("font-weight: bold; color: #d32f2f;")
        h_lab2.addWidget(self.google_deviation_entry)
        h_lab2.addWidget(QLabel("metri"))
        
        h_lab2.addStretch()
        l_lin.addLayout(h_lab2)
        
        l2.addWidget(self.container_linear_opts)
        # ------------------------------------------------------------
        
        l2.addStretch()
            
        # 6. SCANARE
        self.btn_scan_big = QPushButton("🔥 Scanează Raza și Generează Locații", self)
        self.btn_scan_big.setFixedHeight(45)
        self.btn_scan_big.setStyleSheet("background-color: #ff5722; color: white; font-weight: bold; border-radius: 5px; font-size: 12pt;")
        self.btn_scan_big.clicked.connect(self.scan_hotspots)
        l2.addWidget(self.btn_scan_big)
        
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
        
        # --- MODIFICARE: QLineEdit (O singură linie) ---
        self.prompt_entry = QLineEdit()
        self.prompt_entry.setPlaceholderText("ex: farmacie...")
        self.prompt_entry.setFixedHeight(38) 
        self.prompt_entry.setStyleSheet("border: 1px solid #ccc; border-radius: 4px; padding-left: 8px; font-size: 11pt;")
        
        # BONUS: Apăsarea tastei Enter declanșează căutarea
        self.prompt_entry.returnPressed.connect(self.send_request)
        
        h_src.addWidget(self.prompt_entry)
        # -----------------------------------------------
        
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
        
        # 4. FILTRE COMASATE (Rating + Min Voturi)
        h_rate_votes = QHBoxLayout()
        
        # A. Rating Radio
        self.rating_group = QButtonGroup(self)
        h_rate_votes.addWidget(QLabel("Stele:"))
        
        self.radio_any = QRadioButton("Any")
        self.radio_any.setChecked(True)
        self.rating_group.addButton(self.radio_any)
        h_rate_votes.addWidget(self.radio_any)
        
        self.radio_3plus = QRadioButton("⭐ 3+") 
        self.rating_group.addButton(self.radio_3plus)
        h_rate_votes.addWidget(self.radio_3plus)
        
        self.radio_4plus = QRadioButton("⭐ 4+")
        self.rating_group.addButton(self.radio_4plus)
        h_rate_votes.addWidget(self.radio_4plus)
        
        # Spațiu între grupuri
        h_rate_votes.addSpacing(15)
        
        # B. Min Voturi (NOU)
        h_rate_votes.addWidget(QLabel("Min Voturi:"))
        self.search_min_votes_entry = QLineEdit("0")
        self.search_min_votes_entry.setFixedWidth(40)
        self.search_min_votes_entry.setAlignment(Qt.AlignCenter)
        self.search_min_votes_entry.setToolTip("Arată doar locurile cu cel puțin X recenzii")
        h_rate_votes.addWidget(self.search_min_votes_entry)
        
        h_rate_votes.addStretch()
        l3.addLayout(h_rate_votes)
        
        # Obiect ascuns (IMPORTANT: are 'self' ca părinte și .hide() ca să nu apară fereastră fantomă)
        self.route_total_label = QLineEdit("", self)
        self.route_total_label.hide()
        # NOTĂ: Nu mai dăm l3.addWidget, deci nu mai apare dublat în interfață!
        
        l3.addStretch() 
        
        # 5. BUTOANE MICI
        h_small_btns = QHBoxLayout()
        
        b_sav = QPushButton("💾")
        b_sav.setFixedSize(105, 40)
        b_sav.setToolTip("Salvează Traseu")
        b_sav.clicked.connect(self.save_route_to_file)
        h_small_btns.addWidget(b_sav)
        
        b_lod = QPushButton("📂")
        b_lod.setFixedSize(105, 40)
        b_lod.setToolTip("Încarcă Traseu")
        b_lod.clicked.connect(self.load_route_from_file)
        h_small_btns.addWidget(b_lod)
        
        b_ref = QPushButton("🔄")
        b_ref.setFixedSize(105, 40)
        b_ref.setToolTip("Reîmprospătează Info Traseu")
        b_ref.clicked.connect(self.refresh_route_info)
        h_small_btns.addWidget(b_ref)

        # Buton Export Telefon
        b_exp = QPushButton("📲")
        b_exp.setFixedSize(105, 40)
        b_exp.setToolTip("Trimite Traseul pe Telefon (Google Maps)")
        b_exp.clicked.connect(self.export_to_google_maps_url) 
        h_small_btns.addWidget(b_exp)
        
        h_small_btns.addStretch()
        l3.addLayout(h_small_btns)
        
        # 6. BUTON MARE
        b_gen = QPushButton("🗺️ Planifică și Generează Traseu")
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
        # --- FIX: Recunoaștere Traseu la Salvare ---
        elif self.radio_route_mode.isChecked():
            return "route"
        # -------------------------------------------
        else:
            return "text"
    
    def set_search_type(self, value):
        if value == "my_position":
            self.radio_my_position.setChecked(True)
        elif value == "saved_location":
            self.radio_saved_location.setChecked(True)
        elif value == "explore":
            self.radio_explore.setChecked(True)
        # --- FIX: Recunoaștere Traseu la Încărcare ---
        elif value == "route":
            self.radio_route_mode.setChecked(True)
        # ---------------------------------------------
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
    
    def switch_route_mode(self, to_linear=False):
        """Schimbă contextul între Circular și Liniar (A->B)."""
        global selected_places, route_places_coords, linear_places, linear_places_coords, is_linear_mode
        
        # Evităm munca inutilă dacă suntem deja în modul cerut
        if is_linear_mode == to_linear:
            return

        # 1. SALVĂM ORDINEA CURENTĂ (din GUI în Memorie)
        # Astfel, dacă ai reordonat cu drag & drop, nu pierzi ordinea la schimbarea tab-ului
        current_dict = linear_places if is_linear_mode else selected_places
        new_ordered_dict = {}
        
        # Iterăm prin lista vizuală pentru a captura ordinea
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            pid = item.data(Qt.UserRole)
            if pid in current_dict:
                new_ordered_dict[pid] = current_dict[pid]
        
        # Suprascriem memoria veche cu versiunea ordonată
        if is_linear_mode:
            linear_places = new_ordered_dict
        else:
            selected_places = new_ordered_dict

        # 2. SCHIMBĂM MODUL
        is_linear_mode = to_linear
        
        # 3. ACTUALIZĂM INTERFAȚA VIZUALĂ
        self.route_list.clear()
        
        # Ce memorie încărcăm acum?
        target_dict = linear_places if is_linear_mode else selected_places
        
        # Reconstruim lista element cu element
        for pid, data in target_dict.items():
            self.add_to_route_list(
                place_id=pid,
                name=data.get('name', 'Unknown'),
                address=data.get('address', ''),
                rating=data.get('rating', 'N/A'),
                reviews_count=data.get('reviews_count', 0),
                is_open_status=data.get('is_open_status', 'N/A'),
                place_types=data.get('types', []),
                route_info=data.get('route_info'),
                website=data.get('website'),
                update_memory=False # IMPORTANT: Nu vrem să le re-adăugăm în dict, sunt deja acolo
            )
            
        # 4. ACTUALIZĂM TITLUL TABULUI
        mode_label = "Liniar (A->B)" if is_linear_mode else "Circular"
        self.results_tabs.setTabText(1, f"🗺️ Traseu {mode_label} ({self.route_list.count()})")
        
        # 5. VIZIBILITATE CONTROALE (Grupul 2)
        # Ascundem elementele de scanare circulară dacă suntem pe Liniar
        show_circular_tools = not is_linear_mode
        
        # Verificăm dacă elementele există înainte să le ascundem (protecție)
        if hasattr(self, 'show_hotspots_checkbox'): self.show_hotspots_checkbox.setVisible(show_circular_tools)
        if hasattr(self, 'auto_add_hotspots_checkbox'): self.auto_add_hotspots_checkbox.setVisible(show_circular_tools)
        if hasattr(self, 'auto_add_limit_entry'): self.auto_add_limit_entry.setVisible(show_circular_tools)
        if hasattr(self, 'diversity_checkbox'): self.diversity_checkbox.setVisible(show_circular_tools)
        if hasattr(self, 'geo_coverage_checkbox'): self.geo_coverage_checkbox.setVisible(show_circular_tools)
        # Butonul mare de scanare (trebuie să-i fi dat un nume, ex: btn_scan_big)
        # Dacă nu ai variabila salvată, nu o putem ascunde ușor, dar rezolvăm la pasul următor.


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

    def toggle_custom_layer(self, state):
        # 1. Protecție: Dacă harta nu e încărcată, ieșim (evităm ReferenceError)
        if not getattr(self, 'map_is_loaded', False):
            return

        if not custom_manager.is_enabled: 
            return
        
        if state == Qt.Checked.value:
            # Luăm datele și le trimitem la hartă
            all_data = custom_manager.get_all_markers()
            # Convertim în format JSON pt JS
            import json
            js_data = json.dumps(all_data)
            self.web_view.page().runJavaScript(f"addCustomMarkers({js_data});")
        else:
            self.web_view.page().runJavaScript("toggleCustomMarkers(false);")

    
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
        global selected_places, route_places_coords, linear_places_coords, is_linear_mode, linear_places
        
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
        
        # --- [MODIFICARE] SALVARE COORDONATE DUALĂ ---
        if place_id and lat and lng:
            if is_linear_mode:
                linear_places_coords[place_id] = {'lat': lat, 'lng': lng, 'name': name}
            else:
                route_places_coords[place_id] = {'lat': lat, 'lng': lng, 'name': name}
        # ---------------------------------------------
        
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
        
        # --- BUTOANE FUNCȚIONALE ---
        if place_id:
            # 1. Checkbox selectare
            sel_checkbox = QCheckBox()
            sel_checkbox.setStyleSheet("QCheckBox::indicator { width: 26px; height: 26px; }")
            
            # Verificăm în memoria activă
            target_dict = linear_places if is_linear_mode else selected_places
            if place_id in target_dict:
                sel_checkbox.setChecked(True)
                
            p_types = place.get('types', [])
            website_url = place.get('website') # Poate fi None

            sel_checkbox.stateChanged.connect(lambda state, pid=place_id, n=name, r=rating, rc=user_ratings_total, s=is_open, t=p_types, w=website_url: self.toggle_selection(pid, n, r, rc, s, state, t, w))
            header_layout.addWidget(sel_checkbox)
            
            # 2. Buton Website
            web_btn = QPushButton("🌐")
            web_btn.setFixedSize(48, 44)
            web_btn.setStyleSheet("font-size: 18pt; border: 1px solid #ccc; border-radius: 4px; background-color: #f8f9fa;")
            web_btn.clicked.connect(lambda: self.open_website(place_id, name))
            header_layout.addWidget(web_btn)
            
            # 3. Buton AI
            ai_btn = QPushButton("🗣️ Opinii")
            ai_btn.setStyleSheet("font-size: 15pt; padding: 6px 10px; border: 1px solid #b3d9ff; border-radius: 4px; background-color: #e3f2fd; color: #1976d2;")
            ai_btn.clicked.connect(lambda: self.generate_ai_summary_from_card(place_id, name, ai_btn))
            header_layout.addWidget(ai_btn)
            
            # 4. Buton Info/Istoric
            hist_btn = QPushButton("📖 Info")
            hist_btn.setStyleSheet("font-size: 15pt; font-weight: bold; padding: 6px 10px; border: 1px solid #ffe082; border-radius: 4px; background-color: #fff8e1; color: #5d4037;")
            hist_btn.clicked.connect(lambda: self.show_history_window(name, address, hist_btn))
            header_layout.addWidget(hist_btn)
        # --------------------------------------
        
        card_layout.addLayout(header_layout)
        
        # Info line
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
        
        # Status + Distanță
        status_layout = QHBoxLayout()
        status_layout.setSpacing(4)
        
        status_label = QLabel(f"🕒 {is_open}")
        status_label.setStyleSheet("font-size: 15pt; color: #666; border: none;")
        status_layout.addWidget(status_label)
        
        if distance_info and place_id in distance_info:
            dist_data = distance_info[place_id]
            d_text = dist_data.get('distance_text', 'N/A')
            d_dur = dist_data.get('driving_duration', 'N/A')
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

    def add_to_route_list(self, place_id, name, address="", initial_color=None, rating='N/A', reviews_count=0, is_open_status='Program necunoscut', place_types=None, route_info=None, website=None, update_memory=True):
        """Adaugă un element în lista vizuală și (opțional) în memoria activă."""
        
        # --- LOGICĂ MEMORIE DUBLĂ ---
        if update_memory:
            global selected_places, linear_places, is_linear_mode, route_places_coords, linear_places_coords
            
            # Alegem dicționarul activ
            target_dict = linear_places if is_linear_mode else selected_places
            
            # Salvăm datele
            target_dict[place_id] = {
                'name': name,
                'address': address,
                'rating': rating,
                'reviews_count': reviews_count,
                'is_open_status': is_open_status,
                'types': place_types or [],
                'website': website,
                'route_info': route_info
            }
            
            # Gestionăm coordonatele (dacă există în cache-ul global temporar, le mutăm în cel permanent)
            # Verificăm în ambele surse de coordonate posibile
            source_coords = route_places_coords if not is_linear_mode else linear_places_coords
            # Notă: route_places_coords a fost folosit istoric pentru toate. 
            # Acum, dacă suntem pe liniar, ne asigurăm că avem coordonatele și în linear_places_coords
            if is_linear_mode and place_id in route_places_coords:
                linear_places_coords[place_id] = route_places_coords[place_id]
        # ---------------------------

        index = self.route_list.count() + 1
        item = QListWidgetItem()
        item.setData(Qt.UserRole, place_id)
        
        item_widget = RouteItemWidget(place_id, name, address, self, index, initial_color, rating, reviews_count, is_open_status, place_types, route_info, website)
        item_widget.lockChanged.connect(self.on_lock_changed)
        
        item.setSizeHint(item_widget.sizeHint())
        self.route_list.addItem(item)
        self.route_list.setItemWidget(item, item_widget)
        
        self.update_lock_states()
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
        """Elimină o locație din lista vizuală și din memoria activă."""
        global selected_places, linear_places, is_linear_mode
        
        # Alegem dicționarul activ
        target_dict = linear_places if is_linear_mode else selected_places
        
        # Ștergem din memorie
        if place_id in target_dict:
            del target_dict[place_id]
            
        # Ștergem din lista vizuală
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            if item.data(Qt.UserRole) == place_id:
                self.route_list.takeItem(i)
                break
                
        # Actualizări finale
        self.renumber_route_items()
        self.update_lock_states()
        self.save_route_order()
        self.apply_route_filter()
        self.update_route_tab_title()
    
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
        
        # 1. Salvăm starea vizuală curentă (culori și lacăte)
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            pid = item.data(Qt.UserRole)
            w = self.route_list.itemWidget(item)
            if w:
                saved_colors[pid] = getattr(w, 'initial_color', None)
                saved_locks[pid] = w.is_locked()
        
        self.route_list.clear()
        
        # 2. Reconstruim lista în ordinea nouă
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
                
                # --- FIX: EXTRAGEM ȘI WEBSITE-UL ---
                web = d.get('website', None)
                # -----------------------------------
                
                col = saved_colors.get(place_id)
                
                # Îl pasăm mai departe la creare
                self.add_to_route_list(place_id, name, addr, col, rt, rc, st, pt, r_info, website=web)
                
                # Restaurăm lacătul
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
        """Actualizează informațiile prin API Google (V66 - Fix Eroare Types)."""
        global selected_places, linear_places, is_linear_mode
        
        is_silent = silent_mode is True
        
        if self.route_list.count() == 0:
            if not is_silent: QMessageBox.information(self, "Info", "Nu există locații.")
            return
        
        if not is_silent:
            reply = QMessageBox.question(self, "Refresh", "Actualizez datele prin API Google?", QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes: return
        
        try:
            log_info("Se actualizează datele LIVE de la Google...")
            
            target_dict = linear_places if is_linear_mode else selected_places
            route_order = []
            
            # Salvăm ordinea
            for i in range(self.route_list.count()):
                item = self.route_list.item(i)
                pid = item.data(Qt.UserRole)
                route_order.append(pid)
            
            updated_count = 0
            
            for place_id in route_order:
                try:
                    # Păstrăm datele vechi (ca să nu pierdem tipul locului)
                    old_data = target_dict.get(place_id, {})
                    old_name = old_data.get('name', 'Unknown') if isinstance(old_data, dict) else str(old_data)
                    old_types = old_data.get('types', []) # Păstrăm tipurile vechi
                    
                    # --- CAZUL 1: STRAT CUSTOM (Mănăstiri) ---
                    if place_id.startswith("custom_") and custom_manager.is_enabled:
                        cdata = custom_manager.get_place(place_id)
                        if cdata:
                            if place_id in target_dict:
                                target_dict[place_id].update({
                                    'rating': 5.0,
                                    'reviews_count': 99999,
                                    'is_open_status': "Date din Excel",
                                    'address': f"Hram: {cdata['hram']}",
                                    'website': cdata.get('website')
                                })
                            updated_count += 1
                        continue
                    
                    # --- CAZUL 2: WAYPOINT ---
                    if place_id.startswith("waypoint_"): continue
                    
                    # --- CAZUL 3: LOC GOOGLE (FIXED) ---
                    # AM SCOS 'types' DIN LISTA DE CÂMPURI CA SĂ NU MAI DEA EROARE
                    details = gmaps_client.place(
                        place_id=place_id, 
                        fields=['name', 'rating', 'user_ratings_total', 'opening_hours', 'website', 'formatted_address'], 
                        language='ro'
                    )
                    
                    if 'result' in details:
                        res = details['result']
                        
                        new_name = res.get('name', old_name)
                        prefix = ""
                        if old_name.startswith("["):
                            parts = old_name.split(']')
                            if len(parts) > 1: prefix = parts[0] + "] "
                        
                        final_name = prefix + new_name if not new_name.startswith("[") else new_name
                        
                        oh = res.get('opening_hours', {})
                        status = "Program necunoscut"
                        if 'open_now' in oh:
                            status = "Deschis acum" if oh.get('open_now') else "Închis acum"
                            
                        if place_id not in target_dict: target_dict[place_id] = {}
                        
                        # Actualizăm doar ce am primit, păstrăm tipurile vechi
                        target_dict[place_id].update({
                            'name': final_name,
                            'rating': res.get('rating', 0),
                            'reviews_count': res.get('user_ratings_total', 0),
                            'is_open_status': status,
                            'address': res.get('formatted_address', ''),
                            'website': res.get('website'),
                            'types': old_types # Punem la loc tipurile vechi
                        })
                        updated_count += 1
                    
                except Exception as e:
                    log_error(f"Eroare update {place_id}: {e}")
            
            # --- RECONSTRUCȚIE LISTĂ VIZUALĂ ---
            saved_state = {}
            for i in range(self.route_list.count()):
                it = self.route_list.item(i)
                wid = self.route_list.itemWidget(it)
                if wid:
                    saved_state[it.data(Qt.UserRole)] = {
                        'color': getattr(wid, 'initial_color', None),
                        'locked': wid.is_locked()
                    }
            
            self.route_list.clear()
            
            for pid in route_order:
                if pid in target_dict:
                    d = target_dict[pid]
                    state = saved_state.get(pid, {})
                    
                    self.add_to_route_list(
                        pid, 
                        d.get('name', '?'), 
                        d.get('address', ''),
                        state.get('color'), 
                        d.get('rating', 0), 
                        d.get('reviews_count', 0),
                        d.get('is_open_status', '?'),
                        d.get('types', []),
                        d.get('route_info'),
                        website=d.get('website'),
                        update_memory=False
                    )
                    
                    if state.get('locked'):
                        last_item = self.route_list.item(self.route_list.count()-1)
                        if last_item:
                            wid = self.route_list.itemWidget(last_item)
                            if wid: wid.set_locked(True)

            self.renumber_route_items()
            self.update_lock_states()
            
            log_success(f"Date actualizate pentru {updated_count} locații.")
            
        except Exception as e:
            log_error(f"Refresh failed: {e}")
            traceback.print_exc()

    def save_route_to_file(self):
        """Salvează traseul curent (Ordinea exactă + Bifele de fixare + Website)."""
        global selected_places, route_places_coords, linear_places, is_linear_mode, linear_places_coords
        
        if self.route_list.count() == 0:
            QMessageBox.warning(self, "Atenție", "Nu există niciun traseu de salvat!")
            return
        
        # Creăm folderul
        routes_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_routes")
        os.makedirs(routes_folder, exist_ok=True)
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salvează Traseu", routes_folder, "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path: return
        
        import time
        route_data = {
            "version": "1.2", 
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "linear" if is_linear_mode else "circular",
            "places": []
        }
        
        # Alegem sursa de date din memorie (pentru website etc.)
        source_dict = linear_places if is_linear_mode else selected_places
        source_coords = linear_places_coords if is_linear_mode else route_places_coords
        
        # ITERĂM ÎN ORDINEA VIZUALĂ (Asta garantează salvarea ordinii)
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            place_id = item.data(Qt.UserRole)
            widget = self.route_list.itemWidget(item)
            
            # Luăm datele
            web = None
            if place_id in source_dict:
                web = source_dict[place_id].get('website')
            
            place_info = {
                "place_id": place_id,
                "name": widget.name if widget else "Unknown",
                "address": widget.address if widget else "",
                # AICI SALVĂM BIFA (Fixarea)
                "locked": widget.is_locked() if widget else False,
                "initial_color": getattr(widget, 'initial_color', None) if widget else None,
                "website": web
            }
            
            # Adăugăm coordonatele
            if place_id in source_coords:
                coords = source_coords[place_id]
                place_info["lat"] = coords.get("lat")
                place_info["lng"] = coords.get("lng")
            
            route_data["places"].append(place_info)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(route_data, f, ensure_ascii=False, indent=2)
            
            log_success(f"Traseu salvat în: {file_path}")
            QMessageBox.information(self, "Succes", f"Traseul a fost salvat!\n(Ordinea și bifele au fost păstrate)")
        except Exception as e:
            log_error(f"Eroare la salvarea traseului: {e}")
            QMessageBox.critical(self, "Eroare", f"Nu s-a putut salva traseul:\n{e}")


    def load_route_from_file(self):
        """Încarcă un traseu, respectând ordinea și bifele salvate."""
        global selected_places, route_places_coords, linear_places, is_linear_mode, linear_places_coords
        
        routes_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_routes")
        if not os.path.exists(routes_folder):
            routes_folder = os.path.dirname(os.path.abspath(__file__))
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Încarcă Traseu", routes_folder, "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path: return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                route_data = json.load(f)
            
            if "places" not in route_data:
                raise ValueError("Fișier invalid")
            
            # Resetare la cerere
            if self.route_list.count() > 0:
                reply = QMessageBox.question(self, "Traseu Existent", "Înlocuiești traseul curent?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
                if reply == QMessageBox.Cancel: return
                if reply == QMessageBox.Yes:
                    self.clear_route()
            
            target_dict = linear_places if is_linear_mode else selected_places
            target_coords = linear_places_coords if is_linear_mode else route_places_coords
            
            loaded_count = 0
            # ITERĂM LISTA DIN JSON (care e deja ordonată cum trebuie)
            for place_info in route_data["places"]:
                place_id = place_info["place_id"]
                name = place_info.get("name", "Unknown")
                address = place_info.get("address", "")
                locked = place_info.get("locked", False) # Citim starea bifei
                initial_color = place_info.get("initial_color")
                website = place_info.get("website")
                
                # Populăm memoria
                target_dict[place_id] = {
                    'name': name, 
                    'address': address, 
                    'website': website
                }
                
                if "lat" in place_info and "lng" in place_info:
                    target_coords[place_id] = {
                        'lat': place_info["lat"],
                        'lng': place_info["lng"],
                        'name': name
                    }
                
                # Adăugăm în listă (se adaugă la fundul listei, deci ordinea se păstrează)
                self.add_to_route_list(place_id, name, address, initial_color, website=website, update_memory=False)
                
                # RESTAURĂM BIFA (LACĂTUL)
                if locked:
                    last_row = self.route_list.count() - 1
                    item = self.route_list.item(last_row)
                    widget = self.route_list.itemWidget(item)
                    if widget: 
                        widget.set_locked(True) # Asta bifează căsuța
                
                loaded_count += 1
            
            self.update_route_tab_title()
            self.update_lock_states() # Asigurăm că regulile de bife sunt respectate
            self.save_route_order()
            
            log_success(f"Traseu încărcat: {file_path} ({loaded_count} locuri)")
            QMessageBox.information(self, "Succes", f"S-au încărcat {loaded_count} locații.")
            
            # Refresh automat
            QTimer.singleShot(500, lambda: self.refresh_route_info(silent_mode=True))
            
        except Exception as e:
            log_error(f"Eroare încărcare: {e}")
            QMessageBox.critical(self, "Eroare", f"Nu s-a putut încărca:\n{e}")


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


    def calculate_simple_driving_route(self):
        """Calculează un traseu auto simplu între A și B."""
        start_str = self.route_start_entry.text().strip()
        end_str = self.route_end_entry.text().strip()
        
        if not start_str or not end_str:
            QMessageBox.warning(self, "Eroare", "Te rog introdu coordonate pentru Pornire și Destinație.")
            return

        # Validare simplă
        if not parse_coordinates(start_str) or not parse_coordinates(end_str):
            QMessageBox.warning(self, "Eroare", "Format coordonate invalid (ex: 45.123, 23.456).")
            return
            
        self.btn_calc_simple.setText("⏳ Calculez...")
        self.btn_calc_simple.setEnabled(False)
        QApplication.processEvents()
        
        try:
            # 1. Curățăm harta
            self.web_view.page().runJavaScript("if(window.routePolyline) { window.routePolyline.setMap(null); }")
            
            # 2. Apelăm API-ul Google (Mode: DRIVING)
            directions_result = gmaps_client.directions(
                origin=start_str,
                destination=end_str,
                mode="driving",
                alternatives=False,
                language='ro'
            )
            
            if directions_result:
                route = directions_result[0]
                leg = route['legs'][0]
                
                dist_txt = leg['distance']['text']
                dur_txt = leg['duration']['text']
                
                # 3. Desenăm Polilinia
                overview_polyline = route['overview_polyline']['points']
                # Escape backslashes for JS string
                safe_poly = overview_polyline.replace('\\', '\\\\')
                
                js_draw = f"""
                if(window.routePolyline) window.routePolyline.setMap(null);
                var path = google.maps.geometry.encoding.decodePath('{safe_poly}');
                window.routePolyline = new google.maps.Polyline({{
                    path: path,
                    geodesic: true,
                    strokeColor: '#1976D2', // Albastru
                    strokeOpacity: 1.0,
                    strokeWeight: 5,
                    map: map
                }});
                
                // Zoom pe traseu
                var bounds = new google.maps.LatLngBounds();
                path.forEach(function(latLng) {{ bounds.extend(latLng); }});
                map.fitBounds(bounds);
                """
                self.web_view.page().runJavaScript(js_draw)
                
                # 4. Afișăm Rezultatul
                msg = f"🚗 Traseu Auto:\n\n📏 Distanță: {dist_txt}\n⏱️ Timp: {dur_txt}\n\nStart: {leg['start_address']}\nSosire: {leg['end_address']}"
                QMessageBox.information(self, "Rezultat Traseu", msg)
                
                # Update labels adrese
                self.route_start_lbl.setText(f"📍 {leg['start_address'][:40]}...")
                self.route_end_lbl.setText(f"📍 {leg['end_address'][:40]}...")
                
            else:
                QMessageBox.warning(self, "Info", "Nu s-a găsit niciun traseu auto între aceste puncte.")
                
        except Exception as e:
            log_error(f"Eroare traseu simplu: {e}")
            QMessageBox.critical(self, "Eroare API", str(e))
        finally:
            self.btn_calc_simple.setText("🚗 Calculează Traseu Rapid")
            self.btn_calc_simple.setEnabled(True)



    def generate_optimized_route(self):
        """Funcție Bipolară: Generează traseu Circular SAU Liniar în funcție de mod."""
        global selected_places, linear_places, is_linear_mode, route_places_coords, linear_places_coords
        
        # --- RAMURA 1: TRASEU LINIAR (A -> B) ---
        if is_linear_mode:
            start_txt = self.route_start_entry.text().strip()
            end_txt = self.route_end_entry.text().strip()
            
            if not start_txt or not end_txt:
                QMessageBox.warning(self, "Eroare", "Pentru traseu liniar, completează Start (A) și Destinație (B)!")
                return
            
            # 1. CURĂȚENIE GENERALĂ PE HARTĂ (NUKE)
            js_nuke = """
            if(window.routePolyline) { window.routePolyline.setMap(null); }
            if(window.routeMarkers) {
                for(var i=0; i<window.routeMarkers.length; i++) {
                    if(window.routeMarkers[i]) window.routeMarkers[i].setMap(null);
                }
                window.routeMarkers = [];
            }
            """
            self.web_view.page().runJavaScript(js_nuke)
            
            # Colectăm punctele intermediare din lista liniară
            route_order = self.get_route_order()
            
            # Pregătim waypoints
            waypoints = []
            for pid in route_order:
                if pid in linear_places_coords:
                    c = linear_places_coords[pid]
                    waypoints.append(f"{c['lat']},{c['lng']}")
                elif pid in linear_places:
                    waypoints.append(linear_places[pid]['name'])
            
            locked_count = self.get_locked_count()
            do_optimize = (locked_count == 0) 
            
            try:
                log_info(f"Generare Liniar: {start_txt} -> {end_txt} via {len(waypoints)} puncte. Optimizare: {do_optimize}")
                
                res = gmaps_client.directions(
                    origin=start_txt,
                    destination=end_txt,
                    waypoints=waypoints,
                    optimize_waypoints=do_optimize,
                    mode="driving",
                    language='ro'
                )
                
                if res:
                    route = res[0]
                    legs = route['legs']
                    
                    total_km = sum(leg['distance']['value'] for leg in legs)
                    total_sec = sum(leg['duration']['value'] for leg in legs)
                    
                    hours = total_sec // 3600
                    mins = (total_sec % 3600) // 60
                    
                    # Actualizăm textul (care se duce automat în titlul Tab-ului)
                    self.route_total_label.setText(f"🚗 Auto: {total_km/1000:.1f} km • {hours}h {mins}m")
                    # --- FIX: AM SCOS setVisible(True) ---
                    
                    # 2. DESENARE LINIE
                    poly = route['overview_polyline']['points'].replace('\\', '\\\\')
                    self.web_view.page().runJavaScript(f"drawPolyline('{poly}');")
                    
                    # 3. REDESENARE MARKERI
                    markers_data = []
                    for i, pid in enumerate(route_order):
                        lat = None; lng = None; name = f"Punct {i+1}"
                        if pid in linear_places_coords:
                            lat = linear_places_coords[pid]['lat']
                            lng = linear_places_coords[pid]['lng']
                            if pid in linear_places: name = linear_places[pid]['name']
                        
                        if lat is not None:
                            color = None
                            item = self.route_list.item(i)
                            widget = self.route_list.itemWidget(item)
                            if widget: color = getattr(widget, 'initial_color', None)
                            
                            m = {'lat': lat, 'lng': lng, 'name': name, 'index': i+1, 'place_id': pid}
                            if color: m['color'] = color
                            markers_data.append(m)
                    
                    if markers_data:
                        self.web_view.page().runJavaScript(f"addRouteMarkers({json.dumps(markers_data)});")
                    
                    log_success("Traseu Liniar Generat și curățat!")
                else:
                    QMessageBox.warning(self, "Eroare", "Nu s-a găsit traseu.")
                    
            except Exception as e:
                log_error(f"Eroare traseu liniar: {e}")
                QMessageBox.critical(self, "Eroare", str(e))
                
            return 

        # --- RAMURA 2: TRASEU CIRCULAR ---
        route_order = self.get_route_order()
        if len(route_order) < 2:
            QMessageBox.critical(self, "Eroare", "Selectează cel puțin 2 locuri pentru traseu circular!")
            return
            
        for pid in selected_places:
            if 'route_info' in selected_places[pid]: del selected_places[pid]['route_info']
        
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
            log_info("Se calculează traseul PIETONAL (Circular)...")
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
                    total_km += leg['distance']['value']
                    total_min += leg['duration']['value']
                    
                    if i < len(final_order) - 1:
                        dest_id = final_order[i+1]
                        if dest_id in selected_places:
                            selected_places[dest_id]['route_info'] = f"{leg['distance']['text']}, {leg['duration']['text']}"
                
                self.route_total_label.setText(f"🚶 Pietonal: {total_km/1000:.1f} km • {total_min//60} h {total_min%60} min")
                # --- FIX: AM SCOS setVisible(True) ---
                
                poly = route['overview_polyline']['points'].replace('\\', '\\\\')
                self.web_view.page().runJavaScript(f"drawPolyline('{poly}');")
                
                # 3. REDESENARE MARKERI (SINCRONIZAT CU LISTA)
                markers_data = []
                
                # Alegem ordinea corectă în funcție de mod
                target_order = route_order if is_linear_mode else final_order
                target_places = linear_places if is_linear_mode else selected_places
                target_coords = linear_places_coords if is_linear_mode else route_places_coords
                
                for i, pid in enumerate(target_order):
                    # Găsim widget-ul din listă corespunzător acestui ID
                    # (Ca să luăm culoarea exactă pe care o vede utilizatorul)
                    color = None
                    for row in range(self.route_list.count()):
                        item = self.route_list.item(row)
                        if item.data(Qt.UserRole) == pid:
                            widget = self.route_list.itemWidget(item)
                            if widget:
                                color = getattr(widget, 'initial_color', None)
                            break
                    
                    # Dacă nu am găsit widget (ceea ce e rar), calculăm fallback
                    if not color:
                        colors_pool = ['#4285f4', '#ea4335', '#fbbc05', '#34a853', '#9c27b0', '#ff5722', '#00bcd4', '#e91e63', '#795548', '#607d8b']
                        color = colors_pool[i % 10]

                    # Datele locației
                    lat = None; lng = None; name = f"Punct {i+1}"
                    
                    if pid in target_coords:
                        lat = target_coords[pid]['lat']
                        lng = target_coords[pid]['lng']
                        if pid in target_places: 
                            name = target_places[pid].get('name', name)
                    
                    if lat is not None:
                        m = {
                            'lat': lat, 
                            'lng': lng, 
                            'name': name, 
                            'index': i+1, 
                            'place_id': pid,
                            'color': color # TRIMITEM CULOAREA CORECTĂ
                        }
                        markers_data.append(m)
                
                if markers_data:
                    self.web_view.page().runJavaScript(f"addRouteMarkers({json.dumps(markers_data)});")
                
                self.reorder_route_list(final_order)
                log_success("Traseu circular generat.")

        except Exception as e:
            log_error(f"Eroare API: {e}")
            QMessageBox.critical(self, "Eroare", str(e))

    def send_request(self):
        global current_search_results, current_distance_info, saved_locations
        
        # --- SETUP LOGARE ---
        search_log_file = None
        try:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Logs")
            if not os.path.exists(log_dir): os.makedirs(log_dir)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            search_log_file = os.path.join(log_dir, f"Search_{timestamp}.txt")
            
            def log_search_debug(msg):
                try:
                    with open(search_log_file, "a", encoding="utf-8") as f:
                        ts = datetime.datetime.now().strftime("%H:%M:%S")
                        f.write(f"[{ts}] {str(msg)}\n")
                except: pass
            
            print(f"\n>>> [SISTEM] LOG CĂUTARE: {search_log_file}")
            log_search_debug(f"LOG STARTED: {search_log_file}")
        except: 
            def log_search_debug(msg): pass

        self.clear_results()
        log_info("=" * 20 + " CERERE MANUALĂ NOUĂ " + "=" * 20)
        
        search_mode = self.get_search_type()
        
        # Curățare text
        raw_text = self.prompt_entry.text()
        query_text = raw_text.replace("\n", " ").replace("\r", "").strip()
        
        # --- [NOU] CITIRE FILTRU VOTURI ---
        try:
            min_votes_limit = int(self.search_min_votes_entry.text().strip())
        except:
            min_votes_limit = 0
        # ----------------------------------
        
        loading_label = QLabel(f"Se caută '{query_text}' (Min {min_votes_limit} voturi)...")
        italic_font = QFont("Helvetica", 10)
        italic_font.setItalic(True)
        loading_label.setFont(italic_font)
        self.results_layout.addWidget(loading_label)
        QApplication.processEvents()
        
        try:
            results = []
            search_coords = None
            origin_coords = None
            
            # --- COORDONATE ---
            if search_mode == "my_position":
                coords_text = self.my_coords_entry.text().strip()
                search_coords = parse_coordinates(coords_text)
                origin_coords = search_coords
                log_search_debug(f"Mod: Lângă mine ({search_coords})")
            elif search_mode == "saved_location":
                selected_name = self.location_combo.currentText()
                if selected_name in saved_locations:
                    coords_text = saved_locations[selected_name]
                    search_coords = parse_coordinates(coords_text)
                    log_search_debug(f"Mod: Salvat '{selected_name}'")
                origin_coords = parse_coordinates(self.my_coords_entry.text().strip()) if self.use_my_position_for_distance.isChecked() else search_coords
            elif search_mode == "explore":
                coords_text = self.explore_coords_entry.text().strip()
                search_coords = parse_coordinates(coords_text)
                log_search_debug(f"Mod: Explorare ({search_coords})")
                origin_coords = parse_coordinates(self.my_coords_entry.text().strip()) if self.use_my_position_for_distance.isChecked() else search_coords
            
            # --- FETCHING ---
            import time
            if search_mode in ["my_position", "saved_location", "explore"]:
                if not query_text or not search_coords: return

                radius_km_text = self.radius_entry.text().strip()
                radius_in_meters = int(float(radius_km_text.replace(',', '.')) * 1000)
                
                log_search_debug(f"Query: '{query_text}' | Raza: {radius_in_meters}m")
                log_info(f"Căutare '{query_text}' (Rază: {radius_in_meters}m, Min Voturi: {min_votes_limit})")
                
                res = gmaps_client.places_nearby(location=search_coords, radius=radius_in_meters, keyword=query_text, language='ro')
                results = res.get('results', [])
                
                token = res.get('next_page_token')
                pages = 1
                while token and pages < 3:
                    time.sleep(2)
                    try:
                        res_next = gmaps_client.places_nearby(page_token=token, language='ro')
                        results.extend(res_next.get('results', []))
                        token = res_next.get('next_page_token')
                        pages += 1
                    except: break
            
            elif search_mode == "text":
                res = gmaps_client.places(query=query_text, language='ro')
                results = res.get('results', [])

            # --- FILTRARE (Rating + VOTURI) ---
            min_rating = self.get_rating_filter()
            filtered_results = []
            
            log_search_debug(f"Filtrare: Rating {min_rating}, Voturi Min {min_votes_limit}")
            
            for p in results:
                p_votes = p.get('user_ratings_total', 0)
                p_rating = p.get('rating', 0)
                p_name = p.get('name', 'N/A')
                
                # 1. Filtru Voturi
                if p_votes < min_votes_limit:
                    log_search_debug(f"   ❌ Eliminat (Sub {min_votes_limit} voturi): {p_name} ({p_votes})")
                    continue
                
                # 2. Filtru Rating
                if min_rating != "any":
                    if p_rating < int(min_rating):
                        log_search_debug(f"   ❌ Eliminat (Rating mic): {p_name} ({p_rating})")
                        continue
                
                filtered_results.append(p)
                
            results = filtered_results
            
            # --- CALCUL DISTANȚE ---
            distance_info = {}
            if origin_coords and results:
                loading_label.setText("Se calculează distanțele...")
                QApplication.processEvents()
                distance_info = get_distance_info(origin_coords, results)
            
            # --- FILTRARE RUTIERĂ ---
            if search_mode in ["my_position", "saved_location", "explore"] and distance_info:
                try:
                    radius_limit_km = float(self.radius_entry.text().replace(',', '.'))
                    tolerated_limit = radius_limit_km * 1.5
                    strict_results = []
                    for p in results:
                        pid = p.get('place_id')
                        dist_km = distance_info.get(pid, {}).get('distance_km', 999)
                        if dist_km <= tolerated_limit: strict_results.append(p)
                    results = strict_results
                except: pass
            
            # Sortare
            sort_type = self.get_sort_type()
            if sort_type == "rating": results.sort(key=lambda p: p.get('rating', 0), reverse=True)
            elif sort_type == "distance" and distance_info: results.sort(key=lambda p: distance_info.get(p.get('place_id'), {}).get('distance_km', float('inf')))
            
            # Afișare
            loading_label.deleteLater()
            log_success(f"Rezultate finale manuale: {len(results)}")
            log_search_debug(f"REZULTATE FINALE: {len(results)}")
            
            current_search_results = results
            current_distance_info = distance_info
            
            if not results:
                no_results_label = QLabel("Niciun rezultat găsit.")
                self.results_layout.addWidget(no_results_label)
            else:
                self.results_tabs.setTabText(0, f"📋 Rezultate ({len(results)})")
                self.web_view.page().runJavaScript("clearHotspots();")
                search_hotspots = []
                for place in results:
                    self.create_place_card(place, distance_info)
                    loc = place.get('geometry', {}).get('location', {})
                    if loc:
                        search_hotspots.append({
                            'place_id': place.get('place_id'), 'name': place.get('name'),
                            'lat': loc['lat'], 'lng': loc['lng'],
                            'rating': place.get('rating', 0), 'reviews': place.get('user_ratings_total', 0),
                            'types': place.get('types', [])
                        })
                if search_hotspots:
                    js_code = f"addHotspotMarkers({json.dumps(search_hotspots)});"
                    self.web_view.page().runJavaScript(js_code)
                    self.show_hotspots_checkbox.setChecked(True)
            
        except Exception as e:
            log_error(f"Eroare Search: {e}")
            traceback.print_exc()
            self.clear_results()

    def export_to_google_maps_url(self):
        """Generează un link de navigație Google Maps și îl deschide în browser."""
        
        # 1. Obținem ordinea din listă
        count = self.route_list.count()
        if count < 2:
            QMessageBox.warning(self, "Atenție", "Ai nevoie de cel puțin 2 puncte (Start și Destinație) pentru un traseu.")
            return

        waypoints = []
        origin_str = ""
        dest_str = ""
        
        # 2. Extragem coordonatele în ordine
        try:
            for i in range(count):
                item = self.route_list.item(i)
                # Obținem widgetul ca să luăm ID-ul corect
                widget = self.route_list.itemWidget(item)
                pid = widget.place_id
                
                # Căutăm coordonatele exacte în memoria noastră (fie Google, fie Custom)
                if pid in route_places_coords:
                    c = route_places_coords[pid]
                    coord_str = f"{c['lat']},{c['lng']}"
                else:
                    # Fallback (nu ar trebui să se întâmple)
                    coord_str = widget.name
                
                if i == 0:
                    origin_str = coord_str
                elif i == count - 1:
                    dest_str = coord_str
                else:
                    waypoints.append(coord_str)
            
            # 3. Construim URL-ul
            # Format: https://www.google.com/maps/dir/?api=1&origin=...&destination=...&waypoints=...&travelmode=driving
            
            base_url = "https://www.google.com/maps/dir/?api=1"
            
            # Folosim urllib pentru a coda caracterele speciale, deși la coordonate nu e critic
            import urllib.parse
            
            url = f"{base_url}&origin={origin_str}&destination={dest_str}&travelmode=driving"
            
            if waypoints:
                # Waypoints separate prin | (pipe)
                wp_string = "|".join(waypoints)
                url += f"&waypoints={wp_string}"
            
            log_success(f"Link generat: {url}")
            
            # 4. Deschidem în browser
            webbrowser.open(url)
            
            log_info("Link-ul a fost deschis în browser. De acolo îl poți trimite pe telefon.")
            
        except Exception as e:
            log_error(f"Eroare la exportul traseului: {e}")
            QMessageBox.critical(self, "Eroare", f"Nu s-a putut genera link-ul:\n{e}")


    def save_state(self):
        global my_coords_full_address, explore_coords_full_address, gemini_model_value, ai_prompt_var, saved_locations
        global current_map_lat, current_map_lng, current_map_name, current_zoom_level, current_map_place_id, selected_places
        global route_places_coords, linear_places, linear_places_coords, is_linear_mode
        
        # 1. Salvăm datele pentru modul curent
        # (Ca să fim siguri că ce e pe ecran ajunge în variabilele globale înainte de scriere)
        current_dict = linear_places if is_linear_mode else selected_places
        # Aici ar fi bine să facem un update rapid, dar ne bazăm pe faptul că add/remove țin variabilele la zi.

        # Construim lista pentru JSON (doar modul curent vizual, sau ambele?)
        # De obicei salvăm starea vizuală curentă.
        saved_route_data = []
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            widget = self.route_list.itemWidget(item)
            if isinstance(widget, RouteItemWidget):
                # Căutăm coordonatele
                lat, lng = None, None
                # Verificăm în ambele surse
                pid = widget.place_id
                if pid in route_places_coords:
                    lat, lng = route_places_coords[pid]['lat'], route_places_coords[pid]['lng']
                elif pid in linear_places_coords:
                    lat, lng = linear_places_coords[pid]['lat'], linear_places_coords[pid]['lng']

                route_item = {
                    "place_id": widget.place_id,
                    "name": widget.name,
                    "address": widget.address,
                    "locked": widget.is_locked(),
                    "initial_color": getattr(widget, 'initial_color', None),
                    "lat": lat,
                    "lng": lng
                }
                saved_route_data.append(route_item)

        state = {
            # FIX: Folosim .text() pentru QLineEdit
            "search_query": self.prompt_entry.text().strip(),
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
            # FIX: Nu mai citim din widget-ul distanță (că nu există), salvăm 0
            "geo_dist": "0",
            
            # --- SALVARE CUSTOM DATA ---
            "custom_data_path": custom_manager.file_path if custom_manager.is_enabled else "",
            "custom_layer_visible": self.show_custom_checkbox.isChecked()
        }
        
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f, indent=4)
            log_success(f"Starea completă salvată în {STATE_FILE}")
        except Exception as e:
            log_error(f"Nu s-a putut salva starea: {e}")

    def load_state(self):
        global my_coords_full_address, explore_coords_full_address, gemini_model_value, ai_prompt_var, saved_locations, selected_places
        global current_map_lat, current_map_lng, current_map_name, current_zoom_level, current_map_place_id
        global route_places_coords, linear_places, linear_places_coords
        
        if not os.path.exists(STATE_FILE):
            return
        
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            
            self.prompt_entry.setText(state.get("search_query", ""))
            self.my_coords_entry.setText(state.get("my_coords", ""))
            self.explore_coords_entry.setText(state.get("explore_coords", ""))
            self.radius_entry.setText(state.get("radius_km", "1.5"))
            self.set_search_type(state.get("search_type", "my_position"))
            self.set_sort_type(state.get("sort_by", "relevance"))
            self.set_rating_filter(state.get("min_rating", "any"))
            self.use_my_position_for_distance.setChecked(state.get("use_my_position_for_distance", False))
            
            if state.get("my_coords_address"):
                my_coords_full_address = state.get("my_coords_address")
                self.my_coords_address_label.setText(f"📍 {my_coords_full_address[:60]}...")
            if state.get("explore_coords_address"):
                explore_coords_full_address = state.get("explore_coords_address")
                self.explore_address_label.setText(f"📍 {explore_coords_full_address[:60]}...")
            
            map_state = state.get("map_state", {})
            if map_state.get("lat"):
                current_map_lat = map_state.get("lat")
                current_map_lng = map_state.get("lng")
                current_map_name = map_state.get("name")
                current_zoom_level = map_state.get("zoom", 15)
                current_map_place_id = map_state.get("place_id")
            
            self.current_map_type = map_state.get("map_type", "roadmap")
            
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
            # Implicit considerăm că traseul salvat aparține modului curent (Circular)
            # sau ar trebui să salvăm și is_linear_mode în JSON (ar fi ideal pe viitor)
            saved_route = state.get("saved_route", [])
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
                    
                    # Salvăm în selected_places (implicit circular la start)
                    selected_places[pid] = {'name': name, 'address': addr}
                    
                    if "lat" in item_data and "lng" in item_data:
                        route_places_coords[pid] = {
                            'lat': item_data["lat"],
                            'lng': item_data["lng"],
                            'name': name
                        }
                    
                    self.add_to_route_list(pid, name, addr, initial_color, update_memory=True)
                    
                    last_row = self.route_list.count() - 1
                    item = self.route_list.item(last_row)
                    widget = self.route_list.itemWidget(item)
                    if widget: widget.set_locked(locked)
                
                self.update_route_tab_title()
                self.update_lock_states()
            
            filter_idx = state.get("route_filter_index", 0)
            self.route_filter_combo.setCurrentIndex(filter_idx)
            self.apply_route_filter()
            
            if "auto_add_enabled" in state:
                self.auto_add_hotspots_checkbox.setChecked(state["auto_add_enabled"])
            if "auto_add_limit" in state:
                self.auto_add_limit_entry.setText(str(state["auto_add_limit"]))
            if "diversity_enabled" in state:
                self.diversity_checkbox.setChecked(state["diversity_enabled"])
            
            # V3 settings
            if "geo_enabled" in state:
                self.geo_coverage_checkbox.setChecked(state["geo_enabled"])
            if "geo_limit" in state:
                self.geo_limit_entry.setText(str(state["geo_limit"]))
            # FIX: NU mai încercăm să punem text în geo_dist_entry (că nu există)

            # --- RESTAURARE DATE CUSTOM ---
            if state.get("custom_data_path"):
                path = state["custom_data_path"]
                count = custom_manager.load_from_excel(path)
                if count > 0:
                    is_visible = state.get("custom_layer_visible", True)
                    self.show_custom_checkbox.setChecked(is_visible)
                    log_success(f"S-au restaurat {count} mănăstiri. Strat vizibil: {is_visible}")
            
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
        
        # 1. ZOOM LISTENER
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

        # 2. CUSTOM MARKERS LOGIC (AM ADĂUGAT clearCustomMarkers)
        js_custom = """
        window.customMarkers = [];

        function addCustomMarkers(data) {
            if (window.customMarkers) {
                for(let i=0; i<window.customMarkers.length; i++) {
                    window.customMarkers[i].setMap(null);
                }
            }
            window.customMarkers = [];
            
            data.forEach(item => {
                let marker = new google.maps.Marker({
                    position: {lat: item.lat, lng: item.lng},
                    map: map,
                    title: item.name,
                    icon: {
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 6,
                        fillColor: "#8e24aa",
                        fillOpacity: 1,
                        strokeWeight: 1,
                        strokeColor: "white"
                    },
                    zIndex: 1000
                });

                marker.addListener('click', () => {
                    if (window.pyObj) {
                        window.pyObj.receivePOIClick(item.id);
                    }
                });

                window.customMarkers.push(marker);
            });
        }

        function toggleCustomMarkers(show) {
            if (window.customMarkers) {
                window.customMarkers.forEach(m => m.setMap(show ? map : null));
            }
        }

        // --- FUNCȚIA CARE LIPSEA ---
        function clearCustomMarkers() {
            if (window.customMarkers) {
                for(let i=0; i<window.customMarkers.length; i++) {
                    window.customMarkers[i].setMap(null);
                }
            }
            window.customMarkers = [];
        }
        // ---------------------------
        """
        self.web_view.page().runJavaScript(js_custom)
        
        log_success("Browserul a terminat de încărcat harta. Scripturile custom au fost injectate.")
        
        # 3. RESTAURARE STARE HARTĂ
        global current_map_lat, current_map_lng, current_map_name, current_zoom_level, current_map_place_id
        
        if current_map_lat and current_map_lng:
            self.update_map_image(
                current_map_lat, 
                current_map_lng, 
                current_map_name or "Locație Salvată", 
                current_zoom_level, 
                current_map_place_id
            )
        
        if hasattr(self, 'current_map_type') and self.current_map_type:
            js_code = f"setMapType('{self.current_map_type}');"
            self.web_view.page().runJavaScript(js_code)

        # 4. AFIȘARE INITIALĂ CUSTOM
        QTimer.singleShot(1500, lambda: self.toggle_custom_layer(self.show_custom_checkbox.checkState()))


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
        """Scurtătură pentru a pune coordonatele direct în câmpul de explorare ȘI DESTINAȚIE B."""
        
        # 1. Punem textul în câmpul de Explorare (comportament vechi)
        self.explore_coords_entry.setText(coords_text)
        
        # 2. Activăm butonul radio corect
        self.set_search_type("explore")
        
        # 3. Actualizăm harta și adresa pentru Explorare
        self.update_address_and_center_map(
            self.explore_coords_entry,   
            self.explore_address_label,  
            "Zona de explorat",          
            "explore_coords"             
        )
        
        # --- [MODIFICARE NOUĂ] ACTUALIZARE AUTOMATĂ DESTINAȚIE (B) ---
        # Copiem aceleași coordonate și în câmpul de Destinație pentru Traseu
        if hasattr(self, 'route_end_entry'):
            self.route_end_entry.setText(coords_text)
            # Facem și căutarea adresei pentru câmpul B ca să arate frumos
            if hasattr(self, 'route_end_lbl'):
                self.update_address_from_coords(self.route_end_entry, self.route_end_lbl)
        # -------------------------------------------------------------
        
        log_success("Zonă de explorare actualizată (și Destinația B setată).")

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

        if place_id.startswith("custom_"):
            self.show_custom_card(place_id)
            return
        
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
    
    def show_custom_card(self, pid):
        data = custom_manager.get_place(pid)
        if not data: return
        
        self.clear_results()
        self.results_tabs.setCurrentIndex(0)
        
        # Construim Cardul
        card = QFrame()
        card.setFrameShape(QFrame.Box)
        card.setStyleSheet("background-color: #f3e5f5; border: 1px solid #8e24aa; padding: 5px;")
        l = QVBoxLayout(card)
        
        # Titlu
        title = QLabel(f"✞ {data['name']}")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #4a148c;")
        l.addWidget(title)
        
        # Info Grid (Extins)
        grid_w = QWidget(); g = QGridLayout(grid_w)
        
        # Date Tehnice
        g.addWidget(QLabel("<b>Hram:</b>"),0,0); g.addWidget(QLabel(data['hram']),0,1)
        g.addWidget(QLabel("<b>Tip:</b>"),1,0); g.addWidget(QLabel(f"{data['type']} ({data['inhabitants']} viețuitori)"),1,1)
        g.addWidget(QLabel("<b>An:</b>"),2,0); g.addWidget(QLabel(data['year']),2,1)
        
        # Date Administrative (NOU)
        g.addWidget(QLabel("<b>Regiune:</b>"),3,0); g.addWidget(QLabel(data['region']),3,1)
        g.addWidget(QLabel("<b>Arhiepiscopie:</b>"),4,0); g.addWidget(QLabel(data['archdiocese']),4,1)
        g.addWidget(QLabel("<b>Mitropolie:</b>"),5,0); g.addWidget(QLabel(data['metropolis']),5,1)
        
        l.addWidget(grid_w)
        
        # Butoane
        h_btns = QHBoxLayout()
        
        # Buton Web din Excel
        if data['website']:
            btn_web = QPushButton("🌐 Web")
            btn_web.clicked.connect(lambda: webbrowser.open(data['website']))
            h_btns.addWidget(btn_web)
            
        # Checkbox Traseu
        chk_route = QCheckBox("Traseu")
        if pid in selected_places: chk_route.setChecked(True)
        
        chk_route.stateChanged.connect(lambda s: self.toggle_custom_selection(pid, data, s))
        h_btns.addWidget(chk_route)
        
        l.addLayout(h_btns)
        self.results_layout.addWidget(card)
        self.results_layout.addStretch()

    def toggle_custom_selection(self, pid, data, state):
        # Injectăm coordonatele în sistemul global ca să ocolim Google Search
        route_places_coords[pid] = {'lat': data['lat'], 'lng': data['lng'], 'name': data['name']}
        
        # Apelăm funcția veche
        self.toggle_selection(pid, data['name'], "Custom", "N/A", "Deschis", state, ['custom'])


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
        
        # Actualizăm starea UI
        self.update_ui_states()
        
        # Actualizăm adresa și afișăm marker pe hartă
        self.update_address_and_center_map(
            self.explore_coords_entry, 
            self.explore_address_label, 
            "Zona de explorat", 
            "explore_coords"
        )
        
        # --- [MODIFICARE NOUĂ] ACTUALIZARE AUTOMATĂ DESTINAȚIE (B) ---
        if hasattr(self, 'route_end_entry'):
            self.route_end_entry.setText(coords_text)
            if hasattr(self, 'route_end_lbl'):
                self.update_address_from_coords(self.route_end_entry, self.route_end_lbl)
        # -------------------------------------------------------------
        
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
        global route_places_coords, selected_places, diversity_settings, CATEGORIES_MAP, current_log_filename
        
        # --- RAMURA 1: MODUL LINIAR ---
        if self.radio_route_mode.isChecked():
            self.scan_linear_corridor()
            return

        sender_btn = self.sender()
        original_text = ""
        if isinstance(sender_btn, QPushButton):
            if not sender_btn.isEnabled(): return 
            original_text = sender_btn.text()
            sender_btn.setEnabled(False)
            sender_btn.setText("⏳ Scanez...")
            QApplication.processEvents()

        use_custom_data = custom_manager.is_enabled and self.show_custom_checkbox.isChecked()

        # --- LOGGING ---
        try:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Logs")
            if not os.path.exists(log_dir): os.makedirs(log_dir)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            current_log_filename = os.path.join(log_dir, f"Scan_{timestamp}.txt")
            print(f"\n>>> [SISTEM] LOG FILE: {current_log_filename}")
            write_to_file(f"LOG STARTED: {current_log_filename}")
        except Exception as e:
            print(f">>> [EROARE] Log: {e}")

        try:
            log_info("\n" + "="*40)
            log_info("🚀 START SCANARE CIRCULARĂ (V57: Console Clean)")
            log_info("="*40)
            
            self.clear_route() 
            self.clear_results() 

            # --- HELPERE INTERNE ---
            def get_cat(types):
                for k, v in CATEGORIES_MAP.items():
                    if any(t in types for t in v['keywords']): return k
                return 'other'
            
            def is_excluded(types):
                exclude_list = ['lodging', 'parking', 'gas_station', 'atm', 'funeral_home', 'car_repair']
                return any(t in exclude_list for t in types)

            def get_inventory():
                cnts = {k: 0 for k in CATEGORIES_MAP.keys()}
                cnts['other'] = 0
                for pid, data in selected_places.items():
                    pts = data.get('types', [])
                    c = get_cat(pts)
                    if c in cnts: cnts[c] += 1
                    else: cnts['other'] += 1
                return cnts

            # --- INPUTURI ---
            try: min_reviews_threshold = int(self.min_reviews_entry.text().strip())
            except: min_reviews_threshold = 500
            try: limit_v1_total = int(self.auto_add_limit_entry.text().strip())
            except: limit_v1_total = 15
            try: limit_v3_total = int(self.geo_limit_entry.text().strip())
            except: limit_v3_total = 3

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
            
            log_info(f"📍 Centru: {search_coords} | Rază: {radius_m}m")

            candidates_v1 = []; candidates_v2 = []; candidates_v3 = []; seen_ids = set()

            # PAS 0: Custom
            if use_custom_data:
                for cid, cdata in custom_manager.places.items():
                    dist = haversine_distance(search_coords[0], search_coords[1], cdata['lat'], cdata['lng'])
                    if dist <= radius_m:
                        candidates_v1.append({
                            'place_id': cid, 'name': f"[Custom] {cdata['name']}",
                            'lat': cdata['lat'], 'lng': cdata['lng'],
                            'rating': 5.0, 'reviews': 99999, 'types': ['custom_place', 'church'], 'is_custom': True
                        })
                        seen_ids.add(cid)
                        route_places_coords[cid] = {'lat': cdata['lat'], 'lng': cdata['lng'], 'name': cdata['name']}

            # PAS 1: Google Fetch
            import time
            scan_targets = [
                ('tourist_attraction', 3), ('park', 2), ('museum', 2), ('church', 2),
                ('restaurant', 3), ('cafe', 2), ('shopping_mall', 2), ('store', 2)
            ]
            
            log_info("📡 Încep scanarea API (Detalii complete în fișierul LOG)...")
            for p_type, max_pages in scan_targets:
                try:
                    res = gmaps_client.places_nearby(location=search_coords, radius=radius_m, type=p_type, language='ro')
                    results_list = res.get('results', [])
                    token = res.get('next_page_token')
                    pages = 1
                    while token and pages < max_pages:
                        time.sleep(2)
                        try:
                            res_next = gmaps_client.places_nearby(page_token=token, language='ro')
                            results_list.extend(res_next.get('results', []))
                            token = res_next.get('next_page_token')
                            pages += 1
                        except: break
                    
                    for p in results_list:
                        pid = p.get('place_id')
                        if pid in seen_ids: continue
                        rating = p.get('rating', 0); reviews = p.get('user_ratings_total', 0); types = p.get('types', [])
                        name = p.get('name', 'N/A')
                        if rating < 3.0: continue 
                        if is_excluded(types): continue

                        if use_custom_data:
                            g_lat = p['geometry']['location']['lat']; g_lng = p['geometry']['location']['lng']
                            is_dup = False
                            for c_data in custom_manager.places.values():
                                if haversine_distance(g_lat, g_lng, c_data['lat'], c_data['lng']) < 50:
                                    is_dup = True; break
                            if is_dup: continue

                        seen_ids.add(pid)
                        loc = p['geometry']['location']
                        cand = {
                            'place_id': pid, 'name': name, 'lat': loc['lat'], 'lng': loc['lng'],
                            'rating': rating, 'reviews': reviews, 'types': types, 'is_custom': False
                        }
                        if pid and loc['lat']: route_places_coords[pid] = {'lat': loc['lat'], 'lng': loc['lng'], 'name': name}

                        if rating >= 4.0:
                            if reviews >= min_reviews_threshold: candidates_v1.append(cand)
                            else: candidates_v2.append(cand)
                        elif rating >= 3.0:
                            if reviews >= min_reviews_threshold: candidates_v3.append(cand)
                except: pass

            candidates_v1.sort(key=lambda x: x['reviews'], reverse=True) 
            candidates_v2.sort(key=lambda x: x['reviews'], reverse=True) 
            candidates_v3.sort(key=lambda x: x['reviews'], reverse=True)
            
            # --- RAPORTARE ÎN FIȘIER (NU ÎN CONSOLĂ) ---
            log_file_only("\n" + "="*95)
            log_file_only("   🕵️  RAPORT DETALIAT CANDIDAȚI  🕵️")
            log_file_only("="*95)

            def dump_list(label, lst):
                log_file_only(f"\n--- {label} ({len(lst)} locuri) ---")
                if not lst: return
                log_file_only(f"{'NR':<4} | {'NUME':<40} | {'CATEGORIE':<15} | {'RATING':<6} | {'VOTURI':<8} | {'DIST'}")
                log_file_only("-" * 95)
                for i, c in enumerate(lst):
                    dist = haversine_distance(search_coords[0], search_coords[1], c['lat'], c['lng'])
                    name_str = (c['name'][:37] + '..') if len(c['name']) > 37 else c['name']
                    cat_key = get_cat(c['types'])
                    cat_label = CATEGORIES_MAP.get(cat_key, {}).get('label', cat_key)
                    cat_label = cat_label.split(' ')[1] if ' ' in cat_label else cat_label
                    log_file_only(f"{i+1:<4} | {name_str:<40} | {cat_label:<15} | {c['rating']:<6} | {c['reviews']:<8} | {int(dist)}m")

            dump_list("URNA V1", candidates_v1)
            dump_list("URNA V2", candidates_v2)
            dump_list("URNA V3", candidates_v3)
            log_file_only("="*95 + "\n")
            # ---------------------------------------------------

            # Selecție
            taken_ids = set(); v1_cat_counts = {k: 0 for k in CATEGORIES_MAP.keys()}
            count_v1 = 0; count_v2 = 0; count_v3 = 0

            if self.auto_add_hotspots_checkbox.isChecked():
                log_info(f"🌊 [V1] Selecție Vedete")
                for cand in candidates_v1:
                    if count_v1 >= limit_v1_total: break
                    if cand['is_custom']:
                        if not use_custom_data: continue
                        cdata = custom_manager.get_place(cand['place_id'])
                        self.toggle_custom_selection(cand['place_id'], cdata, Qt.Checked.value)
                        count_v1 += 1; taken_ids.add(cand['place_id'])
                        log_success(f"   ✅ [Custom] {cand['name']}")
                        continue
                    cat = get_cat(cand['types'])
                    if cat in diversity_settings:
                        max_allowed = diversity_settings[cat].get('max', 99)
                        if v1_cat_counts.get(cat, 0) >= max_allowed:
                            # LOG DOAR ÎN FIȘIER
                            log_file_only(f"   ❌ [SKIP] {cand['name']} ({cat}): Plafon atins")
                            continue
                    web, stat = self.fetch_details_now(cand['place_id'])
                    self.toggle_selection(cand['place_id'], f"[V1] {cand['name']}", cand['rating'], cand['reviews'], stat, Qt.Checked.value, cand['types'], web)
                    count_v1 += 1; taken_ids.add(cand['place_id']); 
                    if cat in v1_cat_counts: v1_cat_counts[cat] += 1

            if self.diversity_checkbox.isChecked():
                log_info(f"🌊 [V2] Selecție Diversitate")
                for cat, rules in diversity_settings.items():
                    target = rules.get('min', 0); have = get_inventory().get(cat, 0); needed = target - have
                    if needed <= 0: continue
                    added = 0
                    for cand in candidates_v2:
                        if added >= needed: break
                        if cand['place_id'] in taken_ids: continue
                        if get_cat(cand['types']) == cat:
                            web, stat = self.fetch_details_now(cand['place_id'])
                            self.toggle_selection(cand['place_id'], f"[V2] {cand['name']}", cand['rating'], cand['reviews'], stat, Qt.Checked.value, cand['types'], web)
                            count_v2 += 1; taken_ids.add(cand['place_id']); added += 1

            if self.geo_coverage_checkbox.isChecked():
                log_info(f"🌊 [V3] Selecție Populare")
                for cand in candidates_v3:
                    if count_v3 >= limit_v3_total: break
                    if cand['place_id'] in taken_ids: continue
                    web, stat = self.fetch_details_now(cand['place_id'])
                    self.toggle_selection(cand['place_id'], f"[V3] {cand['name']}", cand['rating'], cand['reviews'], stat, Qt.Checked.value, cand['types'], web)
                    count_v3 += 1; taken_ids.add(cand['place_id'])

            # Final
            self.results_tabs.setCurrentIndex(1)
            visual_list = []
            all_found = candidates_v1 + candidates_v2 + candidates_v3
            for cand in all_found:
                if cand['is_custom']:
                    if use_custom_data: visual_list.append(cand)
                    continue
                if cand['reviews'] >= min_reviews_threshold: visual_list.append(cand)
            
            js_code = f"addHotspotMarkers({json.dumps(visual_list)});"
            self.web_view.page().runJavaScript(js_code)
            self.show_hotspots_checkbox.setChecked(True)
            if use_custom_data: self.toggle_custom_layer(Qt.Checked.value)
            else: self.web_view.page().runJavaScript("clearCustomMarkers();")

            # Header
            while self.results_layout.count(): 
                child = self.results_layout.takeAt(0)
                if child.widget(): child.widget().deleteLater()
            
            header = QLabel("🔥 Rezultate Scanare")
            header.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px; color: #2e7d32;")
            self.results_layout.addWidget(header)
            
            # --- AICI E MODIFICAREA: SUMAR DETALIAT ---
            summary_text = (
                f"<b>Total Selectate: {count_v1 + count_v2 + count_v3}</b><br>"
                f"<span style='color:#1565c0;'>[V1] Top: {count_v1}</span> &nbsp;|&nbsp; "
                f"<span style='color:#2e7d32;'>[V2] Diversitate: {count_v2}</span> &nbsp;|&nbsp; "
                f"<span style='color:#e65100;'>[V3] Popular: {count_v3}</span>"
            )
            summary = QLabel(summary_text)
            summary.setStyleSheet("font-size: 11pt; padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
            self.results_layout.addWidget(summary)
            # ------------------------------------------
            
            self.results_layout.addStretch()

        except Exception as e:
            log_error(f"Err: {e}")
            traceback.print_exc()
        finally:
            if current_log_filename:
                write_to_file("LOG ENDED.")
                current_log_filename = None
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




    def scan_linear_corridor(self):
        """LOGICA DE SCANARE PE CORIDOR (Traseu A->B) - V64 (Rezultate Intermediare + Log Clean)."""
        global current_log_filename, linear_places, linear_places_coords, route_places_coords, selected_places
        
        sender_btn = self.sender()
        original_text = ""
        if isinstance(sender_btn, QPushButton):
            original_text = sender_btn.text()
            sender_btn.setEnabled(False)
            sender_btn.setText("🛣️ Scanez Traseu...")
            QApplication.processEvents()

        # Init Log
        try:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Logs")
            if not os.path.exists(log_dir): os.makedirs(log_dir)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            current_log_filename = os.path.join(log_dir, f"ScanRoute_{timestamp}.txt")
            print(f"\n>>> [SISTEM] LOG TRASEU: {current_log_filename}")
            write_to_file(f"LOG TRASEU STARTED: {current_log_filename}")
        except: pass

        try:
            self.clear_results()
            
            log_info("\n" + "="*60)
            log_info("🚀 START SCANARE LINIARĂ (V64: Console Clean)")
            log_info("="*60)
            
            start_txt = self.route_start_entry.text().strip()
            end_txt = self.route_end_entry.text().strip()
            keywords_raw = self.route_keywords_entry.text().strip()
            keywords = [k.strip() for k in keywords_raw.split(',') if k.strip()]
            
            try: scan_step_km = float(self.scan_step_entry.text().strip())
            except: scan_step_km = 10.0
            try: scan_radius_km = float(self.scan_radius_entry.text().strip())
            except: scan_radius_km = 7.0
            try: dev_google_m = float(self.google_deviation_entry.text().strip())
            except: dev_google_m = 100.0
            try: dev_custom_km = float(self.custom_deviation_entry.text().strip())
            except: dev_custom_km = 5.0
            
            log_info(f"Start: {start_txt} -> End: {end_txt}")
            log_info(f"Parametri: Pas={scan_step_km}km, Rază={scan_radius_km}km")

            if not start_txt or not end_txt:
                log_error("Lipsă puncte start/end.")
                return

            log_info("📡 Solicit traseul de la Google...")
            directions = gmaps_client.directions(start_txt, end_txt, mode="driving", language='ro')
            if not directions:
                log_error("Nu s-a găsit traseu.")
                return
            
            route = directions[0]
            overview_poly = route['overview_polyline']['points']
            path_points = decode_polyline(overview_poly)
            
            safe_poly = overview_poly.replace('\\', '\\\\')
            self.web_view.page().runJavaScript(f"drawPolyline('{safe_poly}');")

            scan_points = []
            last_scan_dist = 0
            total_dist = 0
            scan_points.append(path_points[0])
            for i in range(1, len(path_points)):
                p1 = path_points[i-1]; p2 = path_points[i]
                d = haversine_distance(p1[0], p1[1], p2[0], p2[1]) / 1000
                total_dist += d
                if total_dist - last_scan_dist >= scan_step_km:
                    scan_points.append(p2)
                    last_scan_dist = total_dist
            scan_points.append(path_points[-1])
            
            log_info(f"📍 Puncte de scanare (Pioneze): {len(scan_points)}")

            found_places = {} 
            
            # A. CUSTOM LAYER
            if custom_manager.is_enabled and self.show_custom_checkbox.isChecked():
                log_info("🔍 Analizez Stratul Custom pe traseu...")
                for cid, cdata in custom_manager.places.items():
                    min_dist = 99999
                    in_corridor = False
                    for sp in scan_points:
                        if haversine_distance(sp[0], sp[1], cdata['lat'], cdata['lng']) < (scan_radius_km + 20):
                            in_corridor = True; break
                    if in_corridor:
                        for pp in path_points[::5]: 
                            d = haversine_distance(pp[0], pp[1], cdata['lat'], cdata['lng'])
                            if d < min_dist: min_dist = d
                        limit_m = dev_custom_km * 1000
                        if min_dist <= limit_m:
                            found_places[cid] = {
                                'place_id': cid, 'name': f"[Custom] {cdata['name']}",
                                'lat': cdata['lat'], 'lng': cdata['lng'],
                                'rating': 5.0, 'reviews': 99999,
                                'types': ['custom_place'], 'is_custom': True,
                                'vicinity': f"Abatere: {int(min_dist)}m",
                                'opening_hours': {}, 'user_ratings_total': 99999,
                                'geometry': {'location': {'lat': cdata['lat'], 'lng': cdata['lng']}}
                            }
                            log_success(f"   ✅ Găsit Custom: {cdata['name']} (Abatere {int(min_dist)}m)")

            # B. GOOGLE SCAN
            import time
            radius_m = int(scan_radius_km * 1000)
            food_types = ['restaurant', 'cafe', 'bar', 'bakery', 'meal_takeaway', 'meal_delivery', 'food']
            
            log_info(f"📡 Scanez Google în {len(scan_points)} puncte (Detalii în Fișier Log)...")
            
            # --- LOG DOAR ÎN FIȘIER ---
            log_file_only(f"\n--- SCANARE GOOGLE ({len(scan_points)} puncte) ---")
            
            for sp_idx, sp in enumerate(scan_points):
                log_file_only(f"\n📍 PUNCT SCANARE {sp_idx+1}/{len(scan_points)} ({sp})")
                
                for kw in keywords:
                    try:
                        res = gmaps_client.places_nearby(location=sp, radius=radius_m, keyword=kw, language='ro')
                        results = res.get('results', [])
                        
                        if not results:
                            log_file_only(f"   ❓ Keyword '{kw}': 0 rezultate.")
                            continue
                            
                        log_file_only(f"   🔎 Keyword '{kw}': {len(results)} candidați brut.")
                        log_file_only(f"      {'NUME':<35} | {'DIST. PIONEZĂ':<15} | {'ABATERE DRUM':<15} | {'STATUS'}")
                        log_file_only("      " + "-"*85)
                        
                        for p in results:
                            pid = p['place_id']
                            if pid in found_places: continue
                            lat = p['geometry']['location']['lat']; lng = p['geometry']['location']['lng']
                            rating = p.get('rating', 0); types = p.get('types', [])
                            name_str = (p['name'][:32] + '..') if len(p['name']) > 32 else p['name']
                            
                            # Filtru Calitate
                            is_food = any(t in types for t in food_types)
                            if is_food and rating < 4.0:
                                log_file_only(f"      {name_str:<35} | -                | -                | ❌ SKIP CALITATE ({rating} < 4.0)")
                                continue
                            
                            dist_to_center = haversine_distance(sp[0], sp[1], lat, lng)
                            min_dev = 99999
                            for pp in path_points[::10]: 
                                d = haversine_distance(pp[0], pp[1], lat, lng)
                                if d < min_dev: min_dev = d
                            
                            status = ""
                            if min_dev <= dev_google_m:
                                status = "✅ ACCEPTAT"
                                found_places[pid] = {
                                    'place_id': pid, 'name': p['name'], 'lat': lat, 'lng': lng,
                                    'rating': rating, 'user_ratings_total': p.get('user_ratings_total', 0),
                                    'types': types, 'is_custom': False,
                                    'vicinity': p.get('vicinity', ''),
                                    'opening_hours': p.get('opening_hours', {}),
                                    'geometry': p['geometry'] 
                                }
                                # Log success si in consola, ca e important
                                # log_success(f"   + Găsit: {p['name']} (Abatere {int(min_dev)}m)")
                            else:
                                status = f"❌ SKIP (> {int(dev_google_m)}m)"
                            
                            log_file_only(f"      {name_str:<35} | {int(dist_to_center)}m            | {int(min_dev)}m            | {status}")

                    except Exception as e:
                        log_error(f"Err scan '{kw}': {e}")
                
                time.sleep(0.5)

            log_info(f"\n📊 TOTAL ACCEPTATE: {len(found_places)}")
            self.results_tabs.setCurrentIndex(0) 
            self.results_tabs.setTabText(0, f"📋 Rezultate ({len(found_places)})")
            
            visual_list = []
            for pid, data in found_places.items():
                if is_linear_mode:
                    linear_places_coords[pid] = {'lat': data['lat'], 'lng': data['lng'], 'name': data['name']}
                self.create_place_card(data, distance_info=None)
                visual_list.append(data)

            js_code = f"addHotspotMarkers({json.dumps(visual_list)});"
            self.web_view.page().runJavaScript(js_code)
            self.show_hotspots_checkbox.setChecked(True)

        except Exception as e:
            log_error(f"CRASH LINIAR: {e}")
            traceback.print_exc()
        finally:
            if current_log_filename:
                write_to_file("LOG ENDED.")
                current_log_filename = None
            if isinstance(sender_btn, QPushButton):
                sender_btn.setEnabled(True)
                sender_btn.setText(original_text)


    
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
    # --- CURĂȚARE LOGURI VECHI ---
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Logs")
    if os.path.exists(log_dir):
        try:
            shutil.rmtree(log_dir) # Șterge tot folderul
            print(f"[INIT] Folderul Logs a fost golit.")
        except Exception as e:
            print(f"[INIT] Nu s-a putut goli folderul Logs: {e}")
    
    # Recreăm folderul gol
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    # -----------------------------

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
