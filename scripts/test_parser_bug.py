import re

out = """ 0    comment=Full speed group: 14 (PC Wi-Fi) + 18 + 20 + 22 + 23 + 24 + 28 + 29 name=PRIORITY-FULL-GROUP target=192.168.77.16/32,192.168.77.18/32,192.168.77.20/32,\n       192.168.77.22/32,192.168.77.24/32,192.168.77.28/32,192.168.77.29/32 parent=none packet-marks="" priority=1/1 queue=default/default limit-at=0/0 max-limit=1G/1G burst-limit=0/0 burst-threshold=0/0 burst-time=0s/0s bucket-size=0.1/0.1 """

# Faulty parser
faulty_vips = []
for part in out.split():
    if part.startswith("target="):
        targets_raw = part.replace("target=", "").replace('"', '').split(",")
        for t in targets_raw:
            t_clean = t.replace("/32", "").strip()
            if t_clean:
                faulty_vips.append(t_clean)
print("Faulty Parser Result:", faulty_vips)

# Robust Regex parser
match = re.search(r'target=([^\s]+(?:\s+[^\s]+)*?)(?=\s+\w+=|$)', out)
robust_vips = re.findall(r'(\d+\.\d+\.\d+\.\d+)', out.split('parent=')[0] if 'parent=' in out else out)
print("Robust Regex Result (IPs extracted):", robust_vips)
