import os
import shutil
import re

TARGET_FILE = "turist_pro.py"

# Păstrăm blocurile auxiliare la fel, modificăm doar funcția SCAN
NEW_SCAN_FUNC = r'''    def scan_hotspots(self):
        """Scanează zona și aplică algoritmul celor 3 Valuri (V3 STRICT)."""
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
            log_info("🚀 START SCANARE (V3 STRICT: RESPECTĂ LIMITA RECENZII)")
            log_info("="*40)
            
            self.clear_route()
            
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
            loading = QLabel("📡 Scanez satelitul...")
            loading.setStyleSheet("font-size: 12pt; color: #1976d2; padding: 20px;")
            self.results_layout.addWidget(loading)
            QApplication.processEvents()
            
            poi_types = [
                'tourist_attraction', 'museum', 'church', 'place_of_worship',
                'park', 'restaurant', 'cafe', 'bar',
                'shopping_mall', 'store', 'pharmacy', 'bank', 'hospital'
            ]
            
            all_hotspots = []
            seen_ids = set()
            SAFETY_THRESHOLD = 10 
            
            for p_type in poi_types:
                try:
                    res = gmaps_client.places_nearby(location=search_coords, radius=radius_m, type=p_type, language='ro')
                    for p in res.get('results', []):
                        pid = p.get('place_id')
                        if pid in seen_ids: continue
                        revs = p.get('user_ratings_total', 0)
                        if revs < SAFETY_THRESHOLD: continue 
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
                    self.toggle_selection(h['place_id'], display_name, h['rating'], h['reviews'], 'N/A', Qt.Checked.value, h['types'])
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
                    
                    # Diversitatea IGNORĂ limita de 500 (vrea calitate specifică)
                    cands = [h for h in all_hotspots if 
                             h['place_id'] not in selected_places and 
                             h['rating'] >= rules.get('min_rating', 0) and 
                             not is_excluded(h['types']) and 
                             get_cat(h['types']) == cat]
                    cands.sort(key=lambda x: x['reviews'], reverse=True)
                    
                    for h in cands[:needed]:
                        display_name = f"[V2] {h['name']}"
                        self.toggle_selection(h['place_id'], display_name, h['rating'], h['reviews'], 'N/A', Qt.Checked.value, h['types'])
                        total_v2 += 1
                        log_success(f"   + Adăugat: {h['name']}")

            # >>> PASUL 3: GEOGRAFIC (STRICT) <<<
            if self.geo_coverage_checkbox.isChecked():
                try: limit_v3 = int(self.geo_limit_entry.text().strip())
                except: limit_v3 = 3
                
                try: min_dist_m = int(self.geo_dist_entry.text().strip())
                except: min_dist_m = 500 
                
                log_info(f"\n🌊 [V3] Start Val 3: Geografic (Max {limit_v3}, Dist > {min_dist_m}m, STRICT {min_reviews_top}+ Recenzii)")
                
                added_v3 = 0
                
                for h in all_hotspots:
                    if added_v3 >= limit_v3: break
                    
                    # --- FILTRU STRICT PENTRU V3 ---
                    if h['reviews'] < min_reviews_top: continue # Numai locuri "Verzi"
                    
                    if h['place_id'] in selected_places: continue
                    if h['rating'] < 4.0: continue 
                    if is_excluded(h['types']): continue
                    
                    my_lat = h['lat']
                    my_lng = h['lng']
                    is_isolated = True
                    
                    for pid, pdata in selected_places.items():
                        p_coords = route_places_coords.get(pid)
                        if not p_coords:
                             f = next((x for x in all_hotspots if x['place_id'] == pid), None)
                             if f: p_coords = {'lat': f['lat'], 'lng': f['lng']}
                        
                        if p_coords:
                            d = haversine_distance(my_lat, my_lng, p_coords['lat'], p_coords['lng'])
                            if d < min_dist_m:
                                is_isolated = False
                                break
                    
                    if is_isolated:
                        display_name = f"[V3] {h['name']}"
                        special_types = h['types'] + ['poi_geographic']
                        self.toggle_selection(h['place_id'], display_name, h['rating'], h['reviews'], 'N/A', Qt.Checked.value, special_types)
                        added_v3 += 1
                        total_v3 += 1
                        log_success(f"   + Adăugat [V3]: {h['name']} (Zonă nouă!)")

            # --- FINAL ---
            self.clear_results()
            
            visual_hotspots = [h for h in all_hotspots if h['reviews'] >= min_reviews_top]
            if visual_hotspots:
                js_code = f"addHotspotMarkers({json.dumps(visual_hotspots)});"
                self.web_view.page().runJavaScript(js_code)
                self.show_hotspots_checkbox.setChecked(True)
            
            header = QLabel("🔥 Rezultate Scanare")
            header.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px; color: #e65100;")
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
                sender_btn.setText(original_text if original_text else "🔥 Scanează")'''

def apply_scan_update():
    if not os.path.exists(TARGET_FILE):
        print("❌ Lipsă fișier.")
        return

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Înlocuim funcția scan_hotspots
    scan_pattern = r"def scan_hotspots\(self\):.*?(?=def create_hotspot_card)"
    match_scan = re.search(scan_pattern, content, re.DOTALL)
    if match_scan:
        content = content[:match_scan.start()] + NEW_SCAN_FUNC + "\n    " + content[match_scan.end():]
        print("✅ Scan Logic updated (V3 Strict Mode).")
    else:
        print("❌ Nu am găsit funcția scan_hotspots.")

    with open(TARGET_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✨ Gata!")

if __name__ == "__main__":
    apply_scan_update()