import openpyxl
import os
import hashlib

class CustomDataManager:
    def __init__(self):
        self.places = {} # Dicționar cu datele: {'custom_id': {nume, lat, lng...}}
        self.is_enabled = False
        self.file_path = ""
        # Mapare Coloane Excel (A=0, B=1, C=2...)
        self.COL_NAME = 2      # C
        self.COL_VIET = 3      # D
        self.COL_HRAM = 4      # E
        self.COL_TIP = 5       # F
        self.COL_AN = 6        # G
        self.COL_COORDS = 7    # H
        # --- COLONE NOI ---
        self.COL_REG = 8       # I
        self.COL_ARH = 9       # J
        self.COL_MIT = 10      # K

    def load_from_excel(self, path):
        if not os.path.exists(path): return 0
        
        try:
            wb = openpyxl.load_workbook(path, data_only=False)
            ws = wb.active
            self.places.clear()
            count = 0
            
            for row in ws.iter_rows(min_row=2, values_only=False):
                try:
                    c_name = row[self.COL_NAME]
                    c_coords = row[self.COL_COORDS]
                    
                    if not c_name.value or not c_coords.value: continue
                        
                    # 1. Parsare Coordonate
                    coords_txt = str(c_coords.value).replace(';', ',').strip()
                    parts = coords_txt.split(',')
                    lat = float(parts[0].strip())
                    lng = float(parts[1].strip())
                    
                    # 2. Extragere Link
                    website = c_name.hyperlink.target if c_name.hyperlink else ""
                    
                    # 3. Generare ID Unic
                    raw_id = f"{c_name.value}_{lat}_{lng}"
                    pid = f"custom_{hashlib.md5(raw_id.encode()).hexdigest()[:10]}"
                    
                    # 4. Citire Coloane Noi (cu verificare să nu crape dacă lipsesc din excel)
                    val_reg = str(row[self.COL_REG].value or "-") if len(row) > self.COL_REG else "-"
                    val_arh = str(row[self.COL_ARH].value or "-") if len(row) > self.COL_ARH else "-"
                    val_mit = str(row[self.COL_MIT].value or "-") if len(row) > self.COL_MIT else "-"

                    self.places[pid] = {
                        'id': pid,
                        'name': str(c_name.value).strip(),
                        'inhabitants': str(row[self.COL_VIET].value or "?"),
                        'hram': str(row[self.COL_HRAM].value or "-"),
                        'type': str(row[self.COL_TIP].value or "-"),
                        'year': str(row[self.COL_AN].value or "-"),
                        # Date noi:
                        'region': val_reg,
                        'archdiocese': val_arh,
                        'metropolis': val_mit,
                        'lat': lat, 'lng': lng,
                        'website': website,
                        'is_custom': True
                    }
                    count += 1
                except: continue
            
            self.file_path = path
            self.is_enabled = True
            return count
        except Exception as e:
            print(f"Eroare CustomDataManager: {e}")
            return 0

    def get_place(self, pid):
        return self.places.get(pid)

    def get_all_markers(self):
        """Returnează lista pentru hartă."""
        return list(self.places.values())