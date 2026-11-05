import re
import timeit

def without_compile():
    for _ in range(1000):
        re.match(r'^\s*\d+\s+', '  123  ')
        re.search(r'target=([0-9\.\,\s/]+?)(?=\s+(?:parent|packet-marks|priority|queue|limit-at|max-limit|burst|comment)=|$)', 'target=1.1.1.1/32 parent=none', re.DOTALL)
        re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', '1.1.1.1 2.2.2.2')
        re.match(r'^([\d\.]+)([kmg]?bps)$', '1000mbps')

ROS_DETAIL_START_PATTERN = re.compile(r'^\s*\d+\s+')
TARGET_FIELD_PATTERN = re.compile(r'target=([0-9\.\,\s/]+?)(?=\s+(?:parent|packet-marks|priority|queue|limit-at|max-limit|burst|comment)=|$)', re.DOTALL)
IPV4_PATTERN = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
RATE_BPS_PATTERN = re.compile(r'^([\d\.]+)([kmg]?bps)$')

def with_compile():
    for _ in range(1000):
        ROS_DETAIL_START_PATTERN.match('  123  ')
        TARGET_FIELD_PATTERN.search('target=1.1.1.1/32 parent=none')
        IPV4_PATTERN.findall('1.1.1.1 2.2.2.2')
        RATE_BPS_PATTERN.match('1000mbps')

t1 = timeit.timeit(without_compile, number=1000)
t2 = timeit.timeit(with_compile, number=1000)

print(f"Without compile: {t1:.4f}s")
print(f"With compile: {t2:.4f}s")
print(f"Improvement: {(t1-t2)/t1*100:.2f}%")
