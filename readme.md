# Turist Pro 

Aplicație desktop pentru planificarea rutelor turistice cu integrare Google Maps și scanare automată de obiective de interes.

## 📋 Descriere

Turist Pro este o aplicație avansată de planificare a călătoriilor care permite utilizatorilor să:
- Găsească și vizualizeze obiective turistice pe hartă
- Planifice rute personalizate între multiple destinații
- Scaneze automat puncte de interes de-a lungul traseului
- Gestioneze baze de date custom cu locații proprii
- Exporte rute în format KML pentru GPS

![Screenshot aplicație](capture.png)

## ✨ Funcționalități Principale

### 🗺️ Interfață Interactivă cu Hartă
- Vizualizare hartă Google Maps interactivă
- 4 tipuri de hartă: Roadmap, Satellite, Hybrid, Terrain
- Marcare puncte prin click sau căutare
- Drag & drop pentru reordonarea waypoint-urilor
- Preview vizual al rutei planificate

### 🎯 Moduri de Căutare

#### Mod Radial (Căutare Circulară)
- Căutare în rază configurabilă (10-200 km)
- Keywords multiple pentru flexibilitate
- Filtrare automată după calitate (rating ≥4.0 pentru restaurante)
- Sortare după distanță sau rating

#### Mod Liniar (Scanare pe Traseu)
- Scanare automată de-a lungul rutei planificate
- Configurare interval de scanare (5-50 km)
- Deviere permisă configurabilă (500m - 10km)
- Export KML cu toate punctele găsite
- Logging detaliat în fișiere text

### 📊 Date Custom
- Import date din Excel (.xlsx)
- Structură predefinită cu coloane:
  - Nume, Viețuitori, Hram, Tip, An
  - Coordonate GPS
  - Regiune, Arhiepiscopie, Mitropolie
  - Link-uri web
- ID-uri unice generate automat
- Layer vizual separat pe hartă

### 🔍 Filtrare și Sortare Avansată
- Filtrare după rating (1-5 stele)
- Filtrare după număr de recenzii
- Filtrare după tip (custom/Google)
- Sortare după distanță sau popularitate
- Căutare în rezultate

### 💾 Salvare Stare Aplicație
- Ultimele rute folosite
- Preferințe utilizator
- Keywords favorite
- Poziția hărții
- Setări de scanare

## 🛠️ Tehnologii

- **Python 3.8+**
- **PySide6** (Qt6) - Interfață grafică
- **Google Maps API** - Căutare locații și rutare
- **OpenPyXL** - Import date Excel
- **googlemaps-python** - Client API Google

## 📦 Instalare

### Cerințe
```bash
pip install PySide6
pip install googlemaps
pip install openpyxl
pip install python-dotenv
pip install requests
```

### Configurare API Key

1. Obține un API Key de la [Google Cloud Console](https://console.cloud.google.com/)
2. Activează serviciile:
   - Maps JavaScript API
   - Places API
   - Directions API
3. Creează fișier `.env` în directorul aplicației:

```env
GOOGLE_MAPS_API_KEY=your_api_key_here
```

### Structura Fișierelor

```
turist_pro_v05/
├── turist_pro_v05.py          # Aplicația principală
├── custom_data_manager.py      # Manager date custom
├── .env                        # API Key (nu include în Git!)
├── map_template.html           # Template hartă
├── Logs/                       # Directorul de loguri (auto-generat)
└── date_custom.xlsx            # (Opțional) Fișier date custom
```

## 🚀 Utilizare

### Pornire Aplicație
```bash
python turist_pro_v05.py
```

### 1. Setare Punct de Plecare
- **Metoda 1**: Click pe hartă
- **Metoda 2**: Căutare text în câmpul de sus
- **Metoda 3**: Click buton "📍 Locație Curentă" (folosește IP geolocation)

### 2. Căutare Radială

1. Setează raza de căutare (slider 10-200 km)
2. Introdu keywords (ex: "biserică", "mănăstire", "muzeu")
3. Click "🔍 Căutare Radială"
4. Examinează rezultatele în tab "Rezultate"

### 3. Planificare Rută

1. Adaugă waypoint-uri (puncte intermediare):
   - Click "Adaugă Waypoint" și caută locația
   - Sau click direct pe hartă (mod adăugare waypoint activ)
2. Reordonează prin drag & drop în listă
3. Șterge puncte nedorite cu butonul "🗑️"
4. Click "🎯 Calculează Rută" pentru preview
5. Click "🚀 SCANARE LINIARĂ" pentru căutare pe traseu

### 4. Scanare Liniară (Avansată)

Configurare parametri:
- **Interval Scanare**: Distanța între puncte de căutare (5-50 km)
- **Deviere Google**: Cât de departe de traseu să caute în Google (500m-10km)
- **Deviere Custom**: Cât de departe să includă locații custom (0.5-20km)

După scanare:
- Rezultatele apar în tab "Rezultate"
- Se generează fișier de log detaliat în `Logs/`
- Butonul "💾 EXPORT KML" devine activ
- Toate punctele sunt marcate vizual pe hartă

### 5. Export KML

După o scanare liniară:
1. Click "💾 EXPORT KML"
2. Alege locația și numele fișierului
3. Fișierul conține:
   - Traseu complet
   - Toate waypoint-urile
   - Toate locațiile găsite
   - Informații detaliate (rating, reviews, tipuri)

## 📋 Format Date Custom Excel

### Structura Obligatorie

| Coloană | Index | Nume Header | Format | Exemplu |
|---------|-------|-------------|--------|---------|
| C | 2 | Nume | Text | "Biserica Sf. Nicolae" |
| D | 3 | Viețuitori | Număr | "5000" |
| E | 4 | Hram | Text | "Sf. Nicolae" |
| F | 5 | Tip | Text | "Biserică" |
| G | 6 | An | Număr/Text | "1850" |
| H | 7 | Coordonate | "lat,lng" | "47.1585, 27.6014" |
| I | 8 | Regiune | Text | "Moldova" |
| J | 9 | Arhiepiscopie | Text | "Iași" |
| K | 10 | Mitropolie | Text | "Moldovei" |

### Reguli Importante
- Prima linie este header (se ignoră)
- Coordonatele pot fi separate cu `,` sau `;`
- Celulele goale se completează automat cu "-"
- Link-uri web: Adăugă hyperlink pe celula din coloana C (Nume)
- ID-uri unice sunt generate automat pe baza numelui + coordonate

### Exemplu Rând Valid
```
C: Biserica Vovidenia (cu hyperlink către site)
D: 3500
E: Sf. Maria
F: Biserică
G: 1803
H: 47.1585, 27.6014
I: Moldova
J: Iași
K: Moldovei și Bucovinei
```

## ⚙️ Configurări Avansate

### Filtre Calitate
- Restaurante/Cafenele/Baruri: rating minim 4.0 automat
- Alte categorii: fără filtru de rating
- Filtrare după număr recenzii disponibilă în UI

### Parametri de Scanare
```python
# Distanța maximă pentru "în apropiere" în mod radial
MAX_RADIAL_SEARCH = 200_000  # metri

# Interval implicit între scanări
DEFAULT_SCAN_STEP = 20  # km

# Deviere implicită de la traseu
DEFAULT_DEVIATION_GOOGLE = 3000  # metri
DEFAULT_DEVIATION_CUSTOM = 5000  # metri
```

## 📁 Structura Log-urilor

Fișierele de log se generează automat la fiecare scanare:

```
Logs/
└── scan_2025-01-28_143522.txt
```

### Conținut Log
- Timestamp pentru fiecare acțiune
- Parametrii de scanare folosiți
- Număr de puncte de scanare
- Tabel detaliat pentru fiecare candidat:
  - Nume (max 32 caractere)
  - Rating
  - Număr voturi
  - Abatere de la traseu
  - Status (ACCEPTAT/SKIP)
- Statistici finale

### Exemplu Fragment Log
```
[14:35:25] [INFO] 📍 Puncte de scanare (Pioneze): 8
[14:35:26] [DATA] 📍 PUNCT SCANARE 1/8 ((47.158, 27.601))
[14:35:26] [DATA]    🔎 Keyword 'restaurant': 12 candidați brut.
[14:35:26] [DATA]       NUME                             | RAT. | VOTURI | ABATERE    | STATUS
[14:35:26] [DATA]       ------------------------------------------------------------------------------------------
[14:35:26] [DATA]       Restaurant Panoramic            | 4.5  | 324    | 1250m      | ✅ ACCEPTAT
[14:35:26] [DATA]       Bistro La Castel               | 3.8  | 89     | 890m       | ❌ SKIP CALITATE (3.8<4.0)
```

## 🔧 Dezvoltare

### Crearea Executabilului (.exe)

```bash
pip install pyinstaller

pyinstaller --onefile --windowed \
    --add-data "map_template.html;." \
    --add-data ".env;." \
    --icon=icon.ico \
    --name="TuristPro" \
    turist_pro_v05.py
```

### Funcții Ajutătoare Principale

```python
# Calcul distanță între două coordonate
haversine_distance(lat1, lon1, lat2, lon2) -> float

# Decodare polyline Google
decode_polyline(polyline_str) -> List[Tuple[float, float]]

# Distanță punct-linie
point_line_distance(point, start, end) -> float
```

## 🐛 Troubleshooting

### Eroare: "Invalid API Key"
- Verifică fișierul `.env`
- Asigură-te că API-urile sunt activate în Google Cloud Console
- Verifică restricțiile de key (IP, referrer)

### Hartă nu se încarcă
- Verifică conexiunea la internet
- Verifică consolele JavaScript (meniul Debug)
- Regenerează hartă (Meniu → Regenerare Hartă)

### Date Custom nu apar
- Verifică structura Excel (coloane corecte)
- Verifică formatul coordonatelor (lat,lng)
- Verifică log-urile pentru erori de import

### Scanare Liniară lentă
- Reduce numărul de keywords
- Mărește intervalul de scanare
- Reduce raza de scanare

## 📝 Changelog

### v0.5 (Curent)
- ✅ Sistem de logging avansat (consolă + fișier)
- ✅ Tabel detaliat pentru fiecare candidat în scan
- ✅ Export KML funcțional
- ✅ Manager date custom cu 3 coloane noi
- ✅ Filtrare calitate automată
- ✅ UI îmbunătățit cu tabs și iconițe
- ✅ Salvare/restaurare stare aplicație

## 📄 Licență

Acest proiect este proprietate privată. Toate drepturile rezervate.

## 👨‍💻 Autor

Dezvoltat pentru planificarea rutelor turistice și descoperirea obiectivelor de interes în România.

## 📞 Suport

Pentru probleme sau sugestii, consultă log-urile generate sau contactează dezvoltatorul.

---

**Versiune**: 0.5  
**Data**: Noiembrie 2024  
**Status**: Production-Ready
