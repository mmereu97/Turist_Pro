import os
import re

TARGET_FILE = "turist_pro.py"

# Versiunea CORECTĂ și COMPLETĂ a funcției scan_hotspots
NEW_FUNCTION_CODE = r'''    def scan_hotspots(self):
        """Scanează zona vizibilă pentru POI-uri cu multe recenzii (hotspots)."""
        global route_places_coords, selected_places, diversity_settings, CATEGORIES_MAP
        
        log_info("=" * 20 + " SCANARE HOTSPOTS (FIXED) " + "=" * 20)
        
        # 1. Input Utilizator
        try:
            user_min_reviews = int(self.min_reviews_entry.text().strip())
            if user_min_reviews < 1: user_min_reviews = 100
        except:
            user_min_reviews = 100
            
        # 2. Coordonate
        search_coords = None
        search_mode = self.get_search_type()
        
        if search_mode == "my_position":
            coords_text = self.my_coords_entry.text().strip()
            if coords_text: search_coords = parse_coordinates(coords_text)
        elif search_mode == "explore":
            coords_text = self.explore_coords_entry.text().strip()
            if coords_text: search_coords = parse_coordinates(coords_text)
        elif search_mode == "saved_location":
            selected_name = self.location_combo.currentText()
            if selected_name and selected_name in saved_locations:
                coords_text = saved_locations[selected_name]
                search_coords = parse_coordinates(coords_text)
        
        if not search_coords:
            QMessageBox.warning(self, "Eroare", "Nu sunt setate coordonate pentru căutare.")
            return
            
        # 3. Raza
        try:
            radius_m = int(float(self.radius_entry.text().strip()) * 1000)
        except:
            radius_m = 1500
            
        log_info(f"Parametri: Centru={search_coords}, Rază={radius_m}m, Filtru User={user_min_reviews} recenzii")
        
        self.clear_results()
        loading = QLabel("🚀 Scanez satelitul pentru obiective...")
        loading.setStyleSheet("font-size: 12pt; color: #1976d2; padding: 20px;")
        self.results_layout.addWidget(loading)
        QApplication.processEvents()
        
        try:
            # Lista extinsă de tipuri
            poi_types = [
                'tourist_attraction', 'museum', 'church', 'place_of_worship',
                'park', 'restaurant', 'cafe', 'bar',
                'shopping_mall', 'store', 'pharmacy', 'bank', 'hospital'
            ]
            
            all_hotspots = []
            seen_ids = set()
            SAFETY_THRESHOLD = 10 
            
            # COLECTARE DATE
            for p_type in poi_types:
                try:
                    res = gmaps_client.places_nearby(location=search_coords, radius=radius_m, type=p_type, language='ro')
                    places = res.get('results', [])
                    for p in places:
                        pid = p.get('place_id')
                        if pid in seen_ids: continue
                        revs = p.get('user_ratings_total', 0)
                        if revs < SAFETY_THRESHOLD: continue 
                        seen_ids.add(pid)
                        loc = p.get('geometry', {}).get('location', {})
                        hotspot = {
                            'place_id': pid,
                            'name': p.get('name', 'N/A'),
                            'lat': loc.get('lat'),
                            'lng': loc.get('lng'),
                            'rating': p.get('rating', 0),
                            'reviews': revs,
                            'address': p.get('vicinity', ''),
                            'types': p.get('types', [])
                        }
                        all_hotspots.append(hotspot)
                        if pid and loc.get('lat'):
                            route_places_coords[pid] = {'lat': loc['lat'], 'lng': loc['lng'], 'name': hotspot['name']}
                except Exception as e:
                    log_debug(f"Err scan type {p_type}: {e}")

            all_hotspots.sort(key=lambda x: x['reviews'], reverse=True)
            log_success(f"Găsite {len(all_hotspots)} locuri totale (>10 recenzii).")

            # Helper functions
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

            total_added = 0

            # PAS 1: TOP GENERAL (Strict)
            if self.auto_add_hotspots_checkbox.isChecked():
                try:
                    limit_top = int(self.auto_add_limit_entry.text().strip())
                except:
                    limit_top = 15
                
                step1_count = 0
                for h in all_hotspots:
                    if step1_count >= limit_top: break
                    
                    if h['reviews'] < user_min_reviews: continue
                    if h['rating'] < 4.0: continue
                    if h['place_id'] in selected_places: continue
                    if is_excluded(h['types']): continue
                    
                    cat = get_cat(h['types'])
                    inv = get_inventory()
                    if cat in diversity_settings:
                        max_allowed = diversity_settings[cat].get('max', 99)
                        if inv.get(cat, 0) >= max_allowed: continue

                    self.toggle_selection(h['place_id'], h['name'], h['rating'], h['reviews'], 'N/A', Qt.Checked.value, h['types'])
                    step1_count += 1
                    log_success(f"✅ [TOP] {h['name']} ({h['reviews']})")
                
                total_added += step1_count

            # PAS 2: DIVERSITATE (Relaxat)
            if self.diversity_checkbox.isChecked():
                for cat_key, rules in diversity_settings.items():
                    target_min = rules.get('min', 0)
                    if target_min <= 0: continue
                    
                    inv = get_inventory()
                    curr = inv.get(cat_key, 0)
                    needed = target_min - curr
                    if needed <= 0: continue
                    
                    min_rating = rules.get('min_rating', 0)
                    candidates = []
                    for h in all_hotspots:
                        if h['place_id'] in selected_places: continue
                        if h['rating'] < min_rating: continue
                        if is_excluded(h['types']): continue
                        if get_cat(h['types']) == cat_key: candidates.append(h)
                    
                    candidates.sort(key=lambda x: x['reviews'], reverse=True)
                    
                    for h in candidates[:needed]:
                        self.toggle_selection(h['place_id'], h['name'], h['rating'], h['reviews'], 'N/A', Qt.Checked.value, h['types'])
                        total_added += 1
                        log_success(f"⚖️ [DIVERSITATE] {h['name']} ({h['reviews']})")

            self.clear_results()
            
            visual_hotspots = [h for h in all_hotspots if h['reviews'] >= user_min_reviews]
            if visual_hotspots:
                js_code = f"addHotspotMarkers({json.dumps(visual_hotspots)});"
                self.web_view.page().runJavaScript(js_code)
                self.show_hotspots_checkbox.setChecked(True)
            
            header = QLabel(f"🔥 Rezultate Scanare")
            header.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px; color: #e65100;")
            self.results_layout.addWidget(header)
            
            msg = f"Scanat: {len(all_hotspots)} locuri.\\nAdăugat: {total_added} locuri."
            summary = QLabel(msg)
            summary.setStyleSheet("font-size: 11pt; padding: 10px;")
            self.results_layout.addWidget(summary)
            self.results_layout.addStretch()
            
        except Exception as e:
            log_error(f"Eroare la scanarea hotspots: {e}")
            traceback.print_exc()
            self.clear_results()
            error_label = QLabel(f"❌ Eroare: {e}")
            self.results_layout.addWidget(error_label)'''

def fix_file():
    if not os.path.exists(TARGET_FILE):
        print("❌ Nu găsesc fisierul!")
        return

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex pattern pentru a găsi întreaga funcție scan_hotspots
    # Caută "def scan_hotspots(self):" și tot textul până la "def create_hotspot_card"
    pattern = r"def scan_hotspots\(self\):.*?(?=def create_hotspot_card)"
    
    # Verificăm dacă găsim funcția veche (chiar și stricată)
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        print("✅ Am găsit funcția scan_hotspots veche (inclusiv erori). O înlocuiesc complet.")
        new_content = content[:match.start()] + NEW_FUNCTION_CODE + "\n    " + content[match.end():]
        
        with open(TARGET_FILE, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("✨ Fișierul a fost reparat cu succes!")
    else:
        print("❌ Nu am putut identifica funcția scan_hotspots. Verifică manual.")

if __name__ == "__main__":
    fix_file()