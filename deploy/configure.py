"""Configure freshly generated Synapse and mautrix-signal YAML for a private board.
Run from deploy/: python configure.py (requires PyYAML).
Never runs against a live service or rewrites existing registration tokens.
"""
from pathlib import Path
import yaml

signal_path = Path('data/signal/config.yaml')
synapse_path = Path('data/synapse/homeserver.yaml')
signal = yaml.safe_load(signal_path.read_text())
synapse = yaml.safe_load(synapse_path.read_text())
if synapse['server_name'] != 'board.local':
    raise SystemExit('Expected a new private homeserver with server_name board.local')
signal['homeserver'].update(address='http://synapse:8008', domain='board.local', software='standard', websocket=False)
signal['appservice'].update(address='http://signal:29328', hostname='0.0.0.0', port=29328, username_template='signal_{{.}}')
signal['appservice']['bot']['username'] = 'signalbot'
signal['database'].update(type='sqlite3-fk-wal', uri='file:/data/signal.db?_txlock=immediate')
signal['bridge']['permissions'] = {'@board:board.local': 'admin'}
signal['bridge']['personal_filtering_spaces'] = False
signal['matrix'].update(federate_rooms=False, max_download_size=10 * 1024 * 1024)
signal['encryption'].update(allow=False, default=False, require=False)
signal['backfill']['enabled'] = False
signal['network'].update(number_in_topic=False, sync_contacts_on_startup=False, device_name='Slyf Board')
signal['logging'] = {'min_level': 'warn', 'writers': [{'type': 'stdout', 'format': 'json'}]}
synapse['enable_registration'] = False
synapse['app_service_config_files'] = ['/signal-registration.yaml']
synapse['listeners'] = [{'port': 8008, 'tls': False, 'type': 'http', 'x_forwarded': False,
                         'bind_addresses': ['0.0.0.0'], 'resources': [{'names': ['client'], 'compress': False}]}]
synapse['max_upload_size'] = '12M'
synapse['url_preview_enabled'] = False
for path, config in [(signal_path, signal), (synapse_path, synapse)]:
    path.write_text(yaml.safe_dump(config, sort_keys=False))
print('Configured private homeserver and bridge. Generate registration next; see docs/DEPLOYMENT.md.')
