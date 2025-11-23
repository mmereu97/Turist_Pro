import os

def fix_crash_v47():
    input_filename = "turist_pro_v46_final.py"
    output_filename = "turist_pro_v47_final.py"

    if not os.path.exists(input_filename):
        print(f"[EROARE] Nu am găsit fișierul {input_filename}.")
        return

    print(f"[INFO] Citesc {input_filename}...")
    with open(input_filename, "r", encoding="utf-8") as f:
        content = f.read()

    # --- BLOCUL CU PROBLEME (Codul care crapă) ---
    original_crash_block = """        if distance_info and place_id in distance_info:
            dist_data = distance_info[place_id]
            dist_label = QLabel(f"  🚗 {dist_data['distance_text']} • {dist_data['driving_duration']}")
            dist_label.setStyleSheet("color: #1976d2; font-size: 15pt; font-weight: bold; border: none;")
            status_layout.addWidget(dist_label)
            
            if dist_data['walking_duration']:
                walk_label = QLabel(f"  🚶 {dist_data['walking_duration']}")
                walk_label.setStyleSheet("color: #388e3c; font-size: 15pt; font-weight: bold; border: none;")
                status_layout.addWidget(walk_label)"""

    # --- BLOCUL REPARAT (Safe Mode) ---
    # Folosim .get() și verificăm dacă avem structura veche sau cea de POI
    new_safe_block = """        if distance_info and place_id in distance_info:
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
                status_layout.addWidget(walk_label)"""

    # --- ÎNLOCUIRE ---
    if original_crash_block in content:
        new_content = content.replace(original_crash_block, new_safe_block)
        
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        print(f"[SUCCES] V47 Generat: {output_filename}")
        print("Eroarea a fost reparată. Acum poți naviga liniștit între detalii și listă.")
    else:
        print("[EROARE] Nu am găsit blocul de cod specific. Verifică indentarea sau versiunea fișierului.")
        # Debug helper: afișăm primele linii din bloc pentru a ajuta la identificare
        print("Căutam:\n" + original_crash_block[:100] + "...")

if __name__ == "__main__":
    fix_crash_v47()