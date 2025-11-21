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
    # 1. Adăugăm controalele UI pentru Diversitate sub cele existente
    {
        'desc': 'UI: Adaugare rand Diversitate (Diversity Checkbox + Limit)',
        'find': """        auto_add_frame.addStretch()
        hotspot_layout.addLayout(auto_add_frame)
        
        hotspot_layout.addStretch()""",
        'replace': """        auto_add_frame.addStretch()
        hotspot_layout.addLayout(auto_add_frame)

        # --- NOU: Diversitate ---
        diversity_frame = QHBoxLayout()
        self.diversity_checkbox = QCheckBox("⚖️ Diversitate: Asigură")
        self.diversity_checkbox.setToolTip("Asigură un minim de X locuri din fiecare categorie majoră (Cultură, Natură, Mâncare, Shopping)")
        self.diversity_checkbox.setStyleSheet("font-size: 9pt; color: #2e7d32; font-weight: bold;")
        diversity_frame.addWidget(self.diversity_checkbox)
        
        self.diversity_limit_entry = QLineEdit("3")
        self.diversity_limit_entry.setFixedWidth(30)
        diversity_frame.addWidget(self.diversity_limit_entry)
        
        diversity_frame.addWidget(QLabel("din fiecare categ."))
        diversity_frame.addStretch()
        hotspot_layout.addLayout(diversity_frame)
        
        hotspot_layout.addStretch()"""
    },

    # 2. Rescriem logica de Adăugare Automată pentru a include Pasul 2 (Diversitate)
    {
        'desc': 'Logic: Implementare algoritm diversitate (Fill Gaps)',
        'find': """            # --- LOGICĂ NOUĂ: Adăugare Automată ---
            if self.auto_add_hotspots_checkbox.isChecked() and all_hotspots:
                try:
                    max_to_add = int(self.auto_add_limit_entry.text().strip())
                except:
                    max_to_add = 15 # Fallback dacă nu e număr
                
                auto_added = 0
                
                log_info(f"Se procesează adăugarea automată: max {max_to_add} locuri (notă >= 4.0)...")
                
                # Iterăm prin TOATE hotspot-urile găsite până atingem limita
                for h in all_hotspots:
                    if auto_added >= max_to_add:
                        break
                        
                    pid = h['place_id']
                    rating = h.get('rating', 0)
                    
                    # 1. Verificăm dacă există deja
                    if pid in selected_places:
                        continue
                        
                    # 2. Filtru Notă minimă 4.0
                    if rating < 4.0:
                        continue

                    # Adăugăm
                    self.toggle_selection(
                        pid, 
                        h['name'], 
                        rating, 
                        h['reviews'], 
                        'Program necunoscut', 
                        Qt.Checked.value,
                        h.get('types', [])
                    )
                    auto_added += 1
                
                if auto_added > 0:
                    msg = f"S-au adăugat automat {auto_added} locuri de top (⭐4.0+) în traseu."
                    log_success(msg)""",
        'replace': """            # --- LOGICĂ AVANSATĂ: Adăugare Automată + Diversitate ---
            total_added_count = 0
            
            # PASUL 1: Top General (populare)
            if self.auto_add_hotspots_checkbox.isChecked() and all_hotspots:
                try:
                    max_to_add = int(self.auto_add_limit_entry.text().strip())
                except:
                    max_to_add = 15
                
                added_in_step1 = 0
                for h in all_hotspots:
                    if added_in_step1 >= max_to_add: break
                    pid = h['place_id']
                    rating = h.get('rating', 0)
                    
                    if pid in selected_places: continue
                    if rating < 4.0: continue

                    self.toggle_selection(pid, h['name'], rating, h['reviews'], 'Prog. necunoscut', Qt.Checked.value, h.get('types', []))
                    added_in_step1 += 1
                
                total_added_count += added_in_step1

            # PASUL 2: Asigurare Diversitate (Fill Gaps)
            if self.diversity_checkbox.isChecked() and all_hotspots:
                try:
                    min_per_cat = int(self.diversity_limit_entry.text().strip())
                except:
                    min_per_cat = 3
                
                # Definim categoriile majore
                categories_map = {
                    'culture': ['museum', 'art_gallery', 'tourist_attraction', 'church', 'place_of_worship'],
                    'nature': ['park', 'amusement_park', 'natural_feature'],
                    'food': ['restaurant', 'cafe', 'bakery', 'bar'],
                    'shopping': ['shopping_mall', 'department_store', 'clothing_store']
                }
                
                # Helper local pentru detectare categorie
                def get_cat(types):
                    for cat_name, keywords in categories_map.items():
                        if any(k in types for k in keywords):
                            return cat_name
                    return 'other'

                # 1. Numărăm ce avem DEJA în listă (inclusiv ce am adăugat la Pasul 1)
                current_counts = {k: 0 for k in categories_map.keys()}
                for pid, data in selected_places.items():
                    # Dacă avem datele complete în selected_places (types)
                    p_types = data.get('types', [])
                    # Dacă nu le avem (poate au fost adăugate manual fără types), încercăm să le deducem din hotspot list
                    if not p_types:
                        found = next((x for x in all_hotspots if x['place_id'] == pid), None)
                        if found: p_types = found.get('types', [])
                    
                    c = get_cat(p_types)
                    if c in current_counts:
                        current_counts[c] += 1
                
                log_info(f"Status Diversitate curent: {current_counts}. Ținta: {min_per_cat}/cat")
                
                # 2. Completăm lipsurile
                added_diversity = 0
                for cat_name in categories_map:
                    needed = min_per_cat - current_counts[cat_name]
                    if needed <= 0: continue
                    
                    # Căutăm candidați pentru această categorie
                    candidates = []
                    for h in all_hotspots:
                        pid = h['place_id']
                        rating = h.get('rating', 0)
                        if pid in selected_places: continue
                        if rating < 4.0: continue # Respectăm regula de aur
                        
                        if get_cat(h.get('types', [])) == cat_name:
                            candidates.append(h)
                    
                    # Luăm primii N necesari (lista e deja sortată după recenzii)
                    for h in candidates[:needed]:
                        self.toggle_selection(h['place_id'], h['name'], h['rating'], h['reviews'], 'Prog. necunoscut', Qt.Checked.value, h.get('types', []))
                        added_diversity += 1
                        total_added_count += 1
                        log_info(f"➕ Diversitate [{cat_name}]: {h['name']}")

            if total_added_count > 0:
                log_success(f"Total locuri adăugate automat: {total_added_count}")"""
    }
]



if __name__ == "__main__":
    # Când primești cod de la mine, îl vei pune în variabila PATCHES_DATA de mai sus
    if not PATCHES_DATA:
        print("Scriptul de update este gata, dar nu are date. Așteaptă instrucțiuni.")
    else:
        apply_update(PATCHES_DATA)