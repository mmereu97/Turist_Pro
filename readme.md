# 🗺️ TuristPro - Planificator Inteligent de Tururi

O aplicație desktop avansată pentru planificarea și optimizarea tururilor turistice, cu integrare Google Maps și analiză AI a recenziilor.

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.0%2B-green)
![License](https://img.shields.io/badge/license-MIT-blue)

## 📋 Cuprins

- [Caracteristici](#-caracteristici)
- [Capturi de ecran](#-capturi-de-ecran)
- [Cerințe](#-cerințe)
- [Instalare](#-instalare)
- [Configurare](#-configurare)
- [Utilizare](#-utilizare)
- [Funcționalități Detaliate](#-funcționalități-detaliate)
- [Structura Aplicației](#-structura-aplicației)
- [Depanare](#-depanare)
- [Contribuții](#-contribuții)
- [Licență](#-licență)

## ✨ Caracteristici

### 🎯 Funcționalități Principale

- **Căutare Avansată de Locații**: Găsește restaurante, atracții turistice, muzee și alte puncte de interes
- **Hartă Interactivă Google Maps**: Vizualizare live cu markere personalizabile
- **Optimizare Rute**: Algoritm de optimizare TSP (Traveling Salesman Problem) pentru trasee eficiente
- **Analiză AI cu Gemini**: Analiza inteligentă a recenziilor pentru fiecare locație
- **Scanare Hotspots**: Identificare automată a celor mai populare locații din zonă
- **Export GPX**: Export trasee pentru aplicații de navigație (Google Maps, Waze, etc.)

### 🔥 Scanare Hotspots în 3 Valuri

1. **Val 1 - Top Locații**: Cele mai bine cotate și recenzate locații
2. **Val 2 - Diversitate**: Asigură varietate de categorii (restaurante, muzee, parcuri, etc.)
3. **Val 3 - Geografic**: Acoperire geografică completă a zonei

### 🎨 Caracteristici UI/UX

- **Drag & Drop**: Reorganizare intuitivă a traseului
- **Sistem de Tab-uri**: Organizare clară între Rezultate, Traseu și Salvate
- **Salvare Automată**: Starea aplicației se salvează automat
- **Meniu Contextual**: Click dreapta pentru opțiuni rapide
- **Notificări Vizuale**: Feedback instant pentru toate acțiunile

## 🖼️ Capturi de ecran

*Adaugă capturi de ecran ale aplicației tale aici*

## 📦 Cerințe

### Sistem de Operare
- Windows 10/11
- macOS 10.14+
- Linux (Ubuntu 20.04+, Fedora 33+)

### Dependențe Python

```
Python >= 3.8
PySide6 >= 6.0
googlemaps >= 4.10.0
python-dotenv >= 0.19.0
requests >= 2.26.0
```

## 🚀 Instalare

### 1. Clonează Repository-ul

```bash
git clone https://github.com/username/turist-pro.git
cd turist-pro
```

### 2. Creează Mediu Virtual (Recomandat)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalează Dependențele

```bash
pip install -r requirements.txt
```

**requirements.txt:**
```txt
PySide6>=6.0.0
googlemaps>=4.10.0
python-dotenv>=0.19.0
requests>=2.26.0
```

## 🔑 Configurare

### 1. Obține API Keys

#### Google Maps API Key
1. Accesează [Google Cloud Console](https://console.cloud.google.com/)
2. Creează un proiect nou sau selectează unul existent
3. Activează următoarele API-uri:
   - Maps JavaScript API
   - Places API
   - Distance Matrix API
   - Geocoding API
4. Generează un API Key în secțiunea "Credentials"

#### Gemini API Key (Opțional - pentru analiză AI)
1. Accesează [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Generează un API Key nou

### 2. Configurează fișierul .env

Creează un fișier `.env` în directorul principal:

```env
GOOGLE_API_KEY=your_google_maps_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

**⚠️ IMPORTANT**: Nu uita să adaugi `.env` în `.gitignore`!

## 💻 Utilizare

### Pornire Aplicație

```bash
python turist_pro_v47_final.py
```

### Fluxul de Lucru Principal

#### 1️⃣ Setează Locația de Start

```
Tab: "Coordonate Mea" 
→ Introdu adresa sau numele orașului
→ Click "Caută și Actualizează"
```

#### 2️⃣ Caută Locații

```
Tab: "Explorează"
→ Introdu tipul locației (ex: "restaurant", "muzeu")
→ Setează raza de căutare (500m - 50000m)
→ Click "Caută Locații"
```

#### 3️⃣ Scanează Hotspots (Recomandat!)

```
→ Setează parametrii pentru fiecare val:
  • Val 1: Top locații (ex: 5-10)
  • Val 2: Diversitate categorii
  • Val 3: Acoperire geografică
→ Click "🔥 Scanează și Generează"
```

#### 4️⃣ Construiește Traseul

```
→ Bifează locațiile dorite din lista de rezultate
→ SAU drag & drop din tab "Rezultate" în "Traseu"
→ Reordonează prin drag & drop în tab "Traseu"
```

#### 5️⃣ Optimizează și Exportă

```
→ Click "🚀 Optimizează Traseu" pentru rută optimă
→ Click "📥 Export GPX" pentru navigație
→ Click "💾 Salvează Traseu" pentru salvare locală
```

## 🔧 Funcționalități Detaliate

### 🗺️ Sistem de Hartă

- **Markere Multiple**: Diferite culori pentru locații din traseu
- **InfoWindows**: Informații detaliate la click
- **Zoom Sincronizat**: Zoom-ul se păstrează între actualizări
- **Markere Hotspots**: Afișare/ascundere hotspots identificate

### 🎯 Scanare Inteligentă

#### Configurare Diversitate Categorii

Aplicația categorizează automat locațiile în:

- 🍴 **Restaurante & Mâncare**
- ☕ **Cafenele & Patiserii**
- 🍻 **Baruri & Viață de noapte**
- 🏛️ **Muzee & Artă**
- ⛪ **Locuri de cult**
- 📸 **Atracții turistice**
- 🌳 **Parcuri & Natură**
- 🎡 **Zoo & Distracție**
- 🛍️ **Shopping**
- 💊 **Sănătate & Farmacii**
- ⛽ **Utilități**

#### Parametrii Customizabili

Pentru fiecare categorie poți seta:
- **Min**: Număr minim garantat
- **Max**: Plafonare pentru categorii suprapopulate
- **Rating Min**: Filtru calitate (1.0 - 5.0)

### 🤖 Analiză AI (Gemini)

Pentru fiecare locație selectată, AI-ul analizează recenziile și oferă:

1. **Rezumat General**: Impresii generale
2. **Puncte Forte**: 3-5 aspecte apreciate
3. **Puncte Slabe**: 3-5 critici frecvente
4. **Recomandare**: Pentru cine este potrivit

#### Configurare Prompt AI

```python
Setări → Tab "AI Settings" → Editează prompt-ul → Salvează
```

### 📊 Optimizare Traseu

Algoritm TSP cu Distance Matrix API:
- Calculează distanțe reale (nu în linie dreaptă)
- Optimizează pentru timp minim
- Păstrează start-ul fix
- Suportă până la 25 de locații

### 💾 Salvare și Încărcare

#### Salvare Automată
- Starea aplicației se salvează automat în `app_state.json`
- Include coordonate, traseu curent, zoom level

#### Salvare Trasee
```
Format: JSON
Conține: Nume, coordonate, detalii, ordine
Locație: Aleasă de utilizator
```

#### Export GPX
```
Format: GPX (GPS Exchange Format)
Compatibil cu: Google Maps, Waze, Garmin, Strava
Include: Waypoints cu nume și descriere
```

## 📁 Structura Aplicației

```
turist-pro/
│
├── turist_pro_v47_final.py    # Aplicația principală
├── .env                        # Configurare API keys (nu include în Git!)
├── .env.example               # Template pentru .env
├── app_state.json             # Stare aplicație (generat automat)
├── requirements.txt           # Dependențe Python
├── README.md                  # Documentație
│
├── saved_routes/              # Trasee salvate (opțional)
│   ├── traseu_bucuresti.json
│   └── traseu_brasov.json
│
└── exports/                   # Export-uri GPX (opțional)
    ├── tur_paris.gpx
    └── tur_roma.gpx
```

### Clase Principale

#### `MainWindow`
Fereastra principală cu:
- Hartă interactivă (QWebEngineView)
- Sistem de tab-uri (QTabWidget)
- Gestionare evenimente

#### `WebPage`
Pagină web custom pentru:
- Logging erori JavaScript
- Comunicare Python ↔ JavaScript

#### `ClickableLabel`
Widget personalizat pentru:
- Click-uri pe nume locații
- Actualizare hartă

#### `RouteItem`
Element drag & drop pentru:
- Reordonare traseu
- Meniu contextual

### Funcții Utilitare

- `haversine_distance()`: Calcul distanță GPS
- `log_*()`: Sistem de logging colorat
- `fetch_distance_matrix()`: Obține distanțe reale
- `optimize_route_with_dm()`: Optimizare TSP

## 🐛 Depanare

### Probleme Comune

#### 1. Eroare "API Key Invalid"

```
Soluție:
- Verifică că API Key-ul este corect în .env
- Asigură-te că toate API-urile Google Maps sunt activate
- Verifică billing-ul în Google Cloud Console
```

#### 2. Hartă nu se încarcă

```
Soluție:
- Verifică conexiunea la internet
- Deschide Developer Tools (F12) pentru erori JavaScript
- Restart aplicație
```

#### 3. Scanare hotspots nu găsește rezultate

```
Soluție:
- Mărește raza de căutare
- Scade numărul minim de recenzii
- Verifică dacă zona are locații populare
```

#### 4. Export GPX eșuează

```
Soluție:
- Asigură-te că ai permisiuni de scriere
- Verifică că traseul conține locații
- Alege un director diferit
```

### Logging și Debug

Aplicația folosește logging colorat în consolă:
- 🟢 **SUCCESS**: Operații reușite
- 🔴 **ERROR**: Erori critice
- 🟡 **WARNING**: Avertismente
- 🔵 **DEBUG**: Informații detaliate
- 🟣 **INFO**: Informații generale

Pentru debug detaliat, verifică consolă în timpul rulării.

## 🤝 Contribuții

Contribuțiile sunt binevenite! Iată cum poți contribui:

### Raportare Bug-uri

1. Verifică dacă bug-ul nu a fost deja raportat
2. Creează un issue cu:
   - Descriere detaliată
   - Pași de reproducere
   - Screenshot-uri (dacă e relevant)
   - Versiune Python și OS

### Propuneri Funcționalități

1. Deschide un issue de tip "Feature Request"
2. Descrie funcționalitatea dorită
3. Explică cazul de utilizare

### Pull Requests

1. Fork repository-ul
2. Creează un branch pentru feature (`git checkout -b feature/NumeFeature`)
3. Commit schimbările (`git commit -am 'Adaugă feature X'`)
4. Push la branch (`git push origin feature/NumeFeature`)
5. Deschide un Pull Request

### Standarde Cod

- Follow PEP 8 pentru Python
- Adaugă docstrings pentru funcții noi
- Comentează codul complex
- Testează înainte de commit

## 📝 TODO & Roadmap

### Versiuni Viitoare

- [ ] Suport multi-limbă (EN, DE, FR)
- [ ] Integrare cu Weather API
- [ ] Calculare bugete estimative
- [ ] Export PDF cu itinerar complet
- [ ] Sincronizare cloud
- [ ] Aplicație mobilă (React Native)
- [ ] Partajare trasee între utilizatori
- [ ] Sistem de review-uri propriu

### Îmbunătățiri Planificate

- [ ] Mod offline (cached maps)
- [ ] Filtre avansate (preț, timp deschis)
- [ ] Sugestii bazate pe preferințe utilizator
- [ ] Integrare cu calendar
- [ ] Notificări desktop

## 📄 Licență

Acest proiect este licențiat sub licența MIT - vezi fișierul [LICENSE](LICENSE) pentru detalii.

## 👨‍💻 Autor

**Numele Tău**
- GitHub: [@username](https://github.com/username)
- Email: your.email@example.com

## 🙏 Mulțumiri

- Google Maps API pentru date geografice
- Google Gemini AI pentru analiză recenzii
- Comunitatea PySide6 pentru documentație
- Toți contribuitorii și testerii

## 📧 Contact

Pentru întrebări, sugestii sau suport:
- Deschide un [Issue](https://github.com/username/turist-pro/issues)
- Email: your.email@example.com
- Discord: [Server Link](https://discord.gg/yourserver)

---

**Made with ❤️ și ☕ în România**

*Călătorii fericite! 🌍✈️*
