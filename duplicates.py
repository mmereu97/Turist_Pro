filename = "turist_pro.py"
target_line = "scan_hotspots_btn.clicked.connect"

print(f"🔍 Caut duplicate în {filename}...\n")

try:
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    found_at = []
    for i, line in enumerate(lines):
        if target_line in line:
            found_at.append(i + 1) # +1 pentru că liniile încep de la 1

    if len(found_at) == 0:
        print("❌ Nu am găsit linia deloc! (Asta e o problemă)")
    elif len(found_at) == 1:
        print(f"✅ Totul pare OK. Linia apare o singură dată la linia {found_at[0]}.")
    else:
        print(f"🚨 PROBLEMĂ GĂSITĂ! Butonul este conectat de {len(found_at)} ori!")
        print(f"   Liniile: {found_at}")
        print("   De fiecare dată când apeși butonul, se execută câte o funcție pentru fiecare linie de mai sus.")

except FileNotFoundError:
    print("Nu găsesc fișierul turist_pro.py")