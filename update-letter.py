import json
import os
import datetime
import dateutil

from collections import defaultdict
from random import shuffle

from jinja2 import Template, Environment, FileSystemLoader
from pyairtable import Table

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

airtable_id = os.environ.get('AIRTABLE_ID')
airtable_api_key = os.environ.get('AIRTABLE_API_KEY')

# Read in the university domain names list from https://github.com/Hipo/university-domains-list
with open("./world_universities_and_domains.json", encoding='utf-8') as src_file:
    university_domains = json.load(src_file)

# Process domain names to get mappings from domains to countries and country counts
dom2uni = {}
dom2country = {}
uninames = set()
for entry in university_domains:
    uninames.add(entry['name'])
    for domain in entry['domains']:
        dom2uni[domain] = entry['name']
        dom2country[domain] = entry['country']

# Load the signatures data from Airtable, and randomly order
table_name = 'Signatures'
signatures_table = Table(airtable_api_key, airtable_id, table_name)
signatures = signatures_table.all()
# Remove signatures that were withdrawn
signatures = [signature for signature in signatures if not signature['fields'].get('Removals', None)]
# Remove repeated signatures (use the last one)
sigs_with_email = dict()
sigs_without_email = []
for signature in signatures:
    F = signature['fields']
    if 'Email' in F:
        sigs_with_email[F['Email']] = signature # replace
    else:
        sigs_without_email.append(signature)
signatures = list(sigs_with_email.values())+sigs_without_email
# Randomise order
shuffle(signatures)
# Generate reverse ordered signatures
recent_signatures = signatures.copy()
recent_signatures.sort(reverse=True, key=lambda sig: sig['createdTime'])

# Generate stats
country_counts = defaultdict(int)
position_counts = defaultdict(int)
university_counts = defaultdict(int)
uni_name_map = dict()
for row in signatures:
    F = row['fields']
    found_uni = False
    if 'Email' in F:
        try:
            username, domain = F['Email'].split('@')
            if domain in dom2country:
                country_counts[dom2country[domain]] += 1
            if domain in dom2uni:
                university_counts[dom2uni[domain]] += 1
                found_uni = True
        except:
            pass
    if not found_uni and 'Institution' in F and F['Institution'].strip():
        inst = F['Institution']
        if inst.lower().strip() in uni_name_map:
            inst = uni_name_map[inst.lower().strip()]
        else:
            for name in uninames:
                if name.lower().strip() in inst.lower().strip() or inst.lower().strip() in name.lower().strip():
                    uni_name_map[inst.lower().strip()] = name
                    inst = uni_name_map[inst.lower().strip()]
                    break
        university_counts[inst] += 1
    if 'Status' in F:
        position_counts[F['Status']] += 1

# Generate graphs
times = [dateutil.parser.parse(signature['createdTime']) for signature in signatures]
times.sort()
times = np.array(times)
counts = np.arange(len(times))
hours = [datetime.datetime(t.year, t.month, t.day, t.hour, tzinfo=datetime.timezone.utc) for t in times]
hour_counts = defaultdict(int)
for h in hours:
    hour_counts[h] += 1
hours = np.array(list(hour_counts.keys()))
hour_counts = np.array(list(hour_counts.values()))
I = np.argsort(hours)
hours = hours[I]
hour_counts = hour_counts[I]

plt.figure(figsize=(10,8))

plt.subplot(211)
plt.plot(times, counts)
plt.ylabel('Total signatures')
plt.xticks(rotation=70)
plt.title('Cumulative signatures')
plt.grid(visible=True, which='both')

plt.subplot(212)
plt.grid(visible=True, which='both')
plt.bar(hours, hour_counts, width=1/24, align='edge')
plt.ylabel('Signatures per hour')
plt.xticks(rotation=70)
plt.title('Signatures per hour')

plt.tight_layout()

plt.savefig('docs/all_time.png')

last_day_start = datetime.datetime.now(tz=datetime.timezone.utc)-datetime.timedelta(days=1)

plt.figure(figsize=(10,8))

hourloc = mdates.HourLocator(interval = 1)

ax = plt.subplot(211)
plt.plot(times[times>last_day_start], counts[times>last_day_start])
plt.ylabel('Total signatures')
plt.xticks(rotation=70)
plt.title('Cumulative signatures')
plt.grid(visible=True, which='both')
ax.xaxis.set_major_locator(hourloc)

ax = plt.subplot(212)
plt.grid(visible=True, which='both')
plt.bar(hours[hours>last_day_start], hour_counts[hours>last_day_start], width=1/24, align='edge')
plt.ylabel('Signatures per hour')
plt.xticks(rotation=70)
plt.title('Signatures per hour')
ax.xaxis.set_major_locator(hourloc)

plt.tight_layout()

plt.savefig('docs/last24h.png')

# Run templates
env = Environment(loader=FileSystemLoader('templates'))
env.globals.update(
    signatures=signatures,
    recent_signatures=recent_signatures,
    country_counts=country_counts,
    position_counts=position_counts,
    university_counts=university_counts,
    sum=sum,
    )

for page in ['index.html', 'all_signatures.html', 'why.html', 'stats.html', 'share.html', 'league.html', 'graphs.html']:
    pagesrc = env.get_template(page).render(page=page)
    open(f'docs/{page}', 'w', encoding='utf-8').write(pagesrc)
