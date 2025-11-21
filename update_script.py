import os
import shutil

# --- CONFIGURARE ---
TARGET_FILE = "turist_pro.py"
BACKUP_FILE = "turist_pro.py.bak"

def apply_update(patches):
    """
    patches: Lista de dictionare {'find': str, 'replace': str}
    """
    if not os.path.exists(TARGET_FILE):
        print(f"❌ Eroare: Nu găsesc fișierul {TARGET_FILE}")
        return

    # 1. Facem backup automat
    try:
        shutil.copy2(TARGET_FILE, BACKUP_FILE)
        print(f"✅ Backup creat: {BACKUP_FILE}")
    except Exception as e:
        print(f"⚠️ Nu am putut crea backup: {e}")

    # 2. Citim fișierul original
    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # 3. Aplicăm modificările
    updated_content = content
    success_count = 0

    for patch in patches:
        find_str = patch['find']
        replace_str = patch['replace']
        
        if find_str in updated_content:
            updated_content = updated_content.replace(find_str, replace_str)
            success_count += 1
            print(f"🔹 Modificare aplicată: {patch['desc']}")
        else:
            print(f"❌ NU s-a găsit codul pentru: {patch['desc']}")
            # Opțional: Afișăm primii 50 de caractere ca să vedem ce căuta
            print(f"   Căutam: {find_str[:50]}...")

    # 4. Scriem fișierul modificat doar dacă s-au făcut schimbări
    if success_count > 0:
        with open(TARGET_FILE, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        print(f"\n✨ Succes! Au fost aplicate {success_count} modificări în {TARGET_FILE}.")
    else:
        print("\n⚠️ Nicio modificare nu a fost aplicată. Verifică dacă codul sursă corespunde.")

# --- LISTA DE MODIFICĂRI (Aici voi pune eu codul nou de fiecare dată) ---
# Exemplu gol momentan



PATCHES_DATA = [
    # 1. Adăugăm semnalul și slotul în MapBridge (Podul de comunicație)
    {
        'desc': 'MapBridge: Adaugare semnal pentru sincronizare zoom',
        'find': """    # NOU: Semnal pentru setare poziție curentă
    setMyPositionSignal = Signal(float, float)

    @Slot(float, float)
    def receiveMapClick(self, lat, lng):""",
        'replace': """    # NOU: Semnal pentru setare poziție curentă
    setMyPositionSignal = Signal(float, float)
    # NOU: Semnal sincronizare zoom
    zoomChangedSignal = Signal(int)

    @Slot(int)
    def updateZoomLevel(self, zoom):
        \"""Primește nivelul de zoom din JS și îl trimite în Python.\"""
        self.zoomChangedSignal.emit(zoom)

    @Slot(float, float)
    def receiveMapClick(self, lat, lng):"""
    },

    # 2. Conectăm semnalul în MainWindow.__init__
    {
        'desc': 'MainWindow: Conectare semnal zoom',
        'find': """        self.map_bridge.setExploreSignal.connect(self.on_set_explore_from_map)
        self.map_bridge.setMyPositionSignal.connect(self.on_set_my_position_from_map)
        self.channel.registerObject("pyObj", self.map_bridge)""",
        'replace': """        self.map_bridge.setExploreSignal.connect(self.on_set_explore_from_map)
        self.map_bridge.setMyPositionSignal.connect(self.on_set_my_position_from_map)
        # Conectare sincronizare zoom
        self.map_bridge.zoomChangedSignal.connect(self.on_map_zoom_changed)
        self.channel.registerObject("pyObj", self.map_bridge)"""
    },

    # 3. Injectăm "ascultătorul" (Listener) de JavaScript în on_map_ready
    # Asta face ca harta să raporteze automat schimbările
    {
        'desc': 'JS Injection: Adaugare listener zoom_changed in on_map_ready',
        'find': """        self.map_is_loaded = True
        log_success("Browserul a terminat de încărcat harta. Aplicăm starea inițială.")""",
        'replace': """        self.map_is_loaded = True
        
        # --- INJECTARE JS PENTRU SINCRONIZARE ZOOM ---
        # Asta face ca atunci când dai zoom din mouse, Python să afle imediat
        js_zoom_listener = \"""
        if (typeof map !== 'undefined') {
            map.addListener('zoom_changed', function() {
                if (window.pyObj) {
                    window.pyObj.updateZoomLevel(map.getZoom());
                }
            });
        }
        \"""
        self.web_view.page().runJavaScript(js_zoom_listener)
        
        log_success("Browserul a terminat de încărcat harta. Aplicăm starea inițială.")"""
    },

    # 4. Adăugăm funcția Python care actualizează variabila globală
    # O inserăm la finalul clasei MainWindow, înainte de closeEvent
    {
        'desc': 'MainWindow: Adaugare metoda on_map_zoom_changed',
        'find': """    def closeEvent(self, event):
        self.save_state()
        event.accept()""",
        'replace': """    def on_map_zoom_changed(self, zoom):
        \"""Actualizează variabila globală când utilizatorul dă zoom pe hartă.\"""
        global current_zoom_level
        current_zoom_level = zoom
        # log_debug(f"Zoom sincronizat: {zoom}")

    def closeEvent(self, event):
        self.save_state()
        event.accept()"""
    }
]


if __name__ == "__main__":
    # Când primești cod de la mine, îl vei pune în variabila PATCHES_DATA de mai sus
    if not PATCHES_DATA:
        print("Scriptul de update este gata, dar nu are date. Așteaptă instrucțiuni.")
    else:
        apply_update(PATCHES_DATA)