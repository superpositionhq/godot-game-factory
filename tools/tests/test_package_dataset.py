"""tools/package-dataset.py on a throwaway Godot game (the fixture of test_validate_game.py, with a person's commit, a
start branch, a recording, a gameplay recording of the release commit and a player build): the zip it writes, what the
scrub leaves, the sessions' record, what refuses a package, and a mobile game's package (its platform in the manifest,
the APK in Build/, the videos at the phone's size). Plain git and git-lfs; no engine and no PowerShell.

    python -m unittest discover -s tools/tests -p "test_package_dataset.py" -v
"""
import hashlib, io, json, os, re, shutil, subprocess, sys, tempfile, time, unittest, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_validate_game as base  # noqa: E402  the fixture: make_game, task, set_tasks, git, write

TOOLS, SLUG, vg = base.TOOLS, base.SLUG, base.vg
ACCOUNT = 'jtester'
S1, S2, S3 = ('11111111-2222-4333-8444-555555555555', '66666666-7777-4888-9999-aaaaaaaaaaaa', 'bbbbbbbb-cccc-4ddd-8eee-ffffffffffff')
BANNED = re.compile(r'(?i)superposition|game[-_ ]?factory|\banthropic\b|\bclaude\b|\bopenai\b|jtester|jane|tester@|corp\.example')


def row(**kv):
    return json.dumps(kv)


SIZES = {None: (1920, 1080), 'landscape': (1920, 1080), 'portrait': (1080, 1920)}   # a game's frame, by how it is held


def make_inputs(tmp, recorded=True, orientation=None):
    """A game with tasks, one commit by a named person with an agent trailer, a start branch, and next to it the
    recording, the build, the brief files and (recorded) a gameplay recording of the head, without which nothing is
    packaged. orientation: a mobile game held that way (its Platform.json in the person's commit, an APK as its build).
    Returns the paths."""
    root = os.path.join(tmp, 'root')
    repo = os.path.join(root, 'games', SLUG)
    os.makedirs(os.path.dirname(repo))
    start, ref = base.make_game(repo)
    base.write(repo, 'Docs/Notes.md', f'Built on C:\\Users\\{ACCOUNT}\\GodotWork with godot-game-factory and Claude Code.\n'
                                      'Mail jane.tester@corp.example. The Opus run went well; libopus stays.\n'
                                      f'Git Bash ate the backslashes: cd C:Users{ACCOUNT}GodotWorkgames failed.\n'
                                      'The keeper clip is assets/art/Keeper@Walk.fbx (from Keeper.blend).\n')
    base.write(repo, 'Docs/screenshots/kiln.jpg', b'\xff\xd8\xff' + b'\2' * 64)   # an LFS file the README shows
    base.write(repo, 'README.md', '# Kiln Run\n\n![Kiln Run](Docs/screenshots/kiln.jpg)\n\nA game.\n')
    if orientation:
        base.write(repo, vg.PLATFORM_FILE, json.dumps({'platform': 'mobile', 'orientation': orientation}, separators=(',', ':')) + '\n')
        for name, text in zip(('project.godot', 'export_presets.cfg'), base.mobile_files(orientation)):   # as new-game.ps1 lays them
            base.write(repo, name, text)
    base.write(repo, 'Docs/data/tiles.json', json.dumps({'tiles': 'ab12' * 75}) + '\n')   # game data: a long hex value
    env = dict(base.ENV, GIT_AUTHOR_NAME='Jane Tester', GIT_AUTHOR_EMAIL='jane.tester@corp.example',
               GIT_COMMITTER_NAME='Jane Tester', GIT_COMMITTER_EMAIL='jane.tester@corp.example')
    subprocess.run(['git', '-C', repo, 'add', '-A'], check=True, env=env)
    subprocess.run(['git', '-C', repo, 'commit', '-q', '-m', 'Add the notes\n\nBy Jane.\n\nCo-Authored-By: Claude <noreply@anthropic.com>'],
                   check=True, env=env)
    head = base.git(repo, 'rev-parse', 'HEAD')
    when = base.git(repo, 'log', '-1', '--format=%cI', head)
    # a task's own start branch, and a stray branch the delivery must not carry
    base.git(repo, 'branch', f'starts/{SLUG}-fix-hero-hud', start)
    base.git(repo, 'branch', 'experiment', start)
    base.git(repo, 'update-ref', 'refs/remotes/origin/starts/made-elsewhere', start)   # a start branch only origin has
    base.set_tasks(repo, base.game_tasks(start, ref))
    rec = os.path.join(root, '.recording', SLUG)
    cwd = f'C:\\Users\\{ACCOUNT}\\GodotWork\\games\\{SLUG}'
    before, after = when[:11] + '00:00:01' + when[19:], '2099-01-01T00:00:00+00:00'
    base.write(rec, 'actions.jsonl', '\n'.join([
        row(schema='agent-action/v0', time=before, project=SLUG, session_id=S1, agent='claude', event='PostToolUse', cwd=cwd,
            tool='Bash', tool_use_id='t1', input={'command': f'git -C {cwd} log --format=%H -1', 'session_id': S1,
                                                  'cut': f'C:\\Users\\{ACCOUNT}\\AppData\\Local\\Temp\\claude\\C--Users-{ACCOUNT}-GodotWork\\{S1[:16]}',
                                                  'notes': f'C:\\Users\\{ACCOUNT}\\AppData\\Roaming\\Claude\\side-session-notes\\local_{S1}\\notes.md'},
            response=f'{ref}\nsee C:\\Users\\{ACCOUNT}\\GodotWork\\godot-game-factory\\tools ' + 'QUJD' * 100),
        row(schema='agent-action/v0', time=before, project=SLUG, session_id=S2, agent='codex', event='PostToolUse', cwd=cwd,
            tool='apply_patch', tool_use_id='t2', input={'command': '*** Begin Patch'}, response='ok: runs/pilot-2c-opus-siege/summary.json'),
        # a tool call's whole output (far past the 8,000 characters rows held before), a name deep inside it; and one cut at the cap
        row(schema='agent-action/v0', time=before, project=SLUG, session_id=S2, agent='codex', event='PostToolUse', cwd=cwd,
            tool='Bash', tool_use_id='t4', input={'command': 'type build.log'},
            response='compiling\n' * 3000 + f'saved to C:\\Users\\{ACCOUNT}\\GodotWork\\out.txt for jane.tester@corp.example'),
        row(schema='agent-action/v0', time=before, project=SLUG, session_id=S2, agent='codex', event='PostToolUse', cwd=cwd,
            tool='Bash', tool_use_id='t5', input={'command': 'type big.log'}, response='x' * 500, response_chars=2000000, response_truncated=True),
        row(schema='agent-action/v0', time=before, project=SLUG, session_id=S3, agent='claude', event='PostToolUse', cwd=cwd,
            tool='Bash', tool_use_id='t3', input={'command': 'python tools/package-dataset.py kiln-run'}, response='ok'),
        row(schema='agent-action/v0', time=after, project=SLUG, session_id=S1, agent='claude', event='Stop', cwd=cwd)]) + '\n')
    base.write(rec, 'messages.jsonl', '\n'.join([
        row(schema='agent-message/v0', time=before, project=SLUG, session_id=S1, agent='claude', role='user', message_id='m1',
            text='Keep the hero on the ground. Ask jane.tester@corp.example if Superposition agrees.'),
        row(schema='agent-message/v0', time=before, project=SLUG, session_id=S1, agent='claude', role='assistant', message_id='m2',
            model='claude-opus-5-5', text='Done by Claude; OpenAI was not used.'),
        row(schema='agent-message/v0', time=before, project=SLUG, session_id=S1, agent='claude', role='thinking', message_id='m2:thinking',
            model='claude-opus-5-5', text='Claude should mail jane.tester@corp.example about the hero.'),
        row(schema='agent-message/v0', time=before, project=SLUG, session_id=S1, agent='claude', role='thinking', message_id='m2b:thinking',
            redacted=True, text=''),
        row(schema='agent-message/v0', time=before, project=SLUG, session_id=S2, agent='codex', role='user', message_id='m3', text='Add the HUD.'),
        row(schema='agent-message/v0', time=before, project=SLUG, session_id=S3, agent='claude', role='user', message_id='m4', text='Package it.'),
        row(schema='agent-message/v0', time=after, project=SLUG, session_id=S1, agent='claude', role='user', message_id='m5', text='Later.')]) + '\n')
    build = os.path.join(tmp, 'build')
    for rel, data in ((('KilnRun.apk', APK),) if orientation else (('KilnRun.exe', b'MZ' + b'\0' * 30), ('KilnRun.pck', b'GDPC' + b'\0' * 28))):
        base.write(build, rel, data)
    base.write(tmp, 'brief.md', '# Brief\n\n' + 'Build a small kiln game. ' * 20)
    base.write(tmp, 'design.md', '# Design\n\n' + 'Systems, scenes and scenarios. ' * 20)
    inp = dict(root=root, repo=repo, build=build, head=head, start=start, ref=ref, orientation=orientation,
               brief=os.path.join(tmp, 'brief.md'), design=os.path.join(tmp, 'design.md'))
    if recorded:
        record(inp)
    return inp


def run(inp, *extra, env=None, build=True, brief=True):
    # GGF_OUT and GGF_CONFIG inside the test's folder: what the packager keeps in the out folder stays there, and no test
    # reads this machine's config
    env = dict(dict(base.ENV, GGF_ROOT=inp['root'], GGF_OUT=os.path.join(inp['root'], 'deliverables'),
                    GGF_CONFIG=os.path.join(inp['root'], 'no-config.json'), GGF_MIN_FREE_GB='0', USERNAME=ACCOUNT,
                    COMPUTERNAME='JT-DESKTOP'), **(env or {}))
    args = [sys.executable, os.path.join(TOOLS, 'package-dataset.py'), SLUG, '--version', '1.0']
    args += ['--build', inp['build']] if build else []
    args += ['--brief', inp['brief'], '--design', inp['design']] if brief else []
    return subprocess.run(args + list(extra), capture_output=True, text=True, env=env)


PKG = base.load('package_dataset', 'package-dataset.py')
_PROBE = PKG.find_ffprobe()   # this machine's ffmpeg, when it has one: the videos are then real ones a probe accepts
FFMPEG = _PROBE and os.path.join(os.path.dirname(_PROBE), os.path.basename(_PROBE).replace('ffprobe', 'ffmpeg'))
_MP4 = {}
APK = b'PK\x03\x04' + b'\0' * 60   # stands for an Android package


def gameplay_mp4(size=(1920, 1080)):
    """An mp4 the layout accepts (h264 of the given size + aac, one second) when ffmpeg is here, else bytes no probe
    reads (the validators then note that the videos were not probed)."""
    if size not in _MP4:
        data = b'\0\0\0\x18ftypmp42' + bytes(range(256)) * 4 + ('%dx%d' % size).encode()
        if FFMPEG and os.path.isfile(FFMPEG):
            out = os.path.join(tempfile.mkdtemp(prefix='ggfv'), 'v.mp4')
            r = subprocess.run([FFMPEG, '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=%dx%d:r=60:d=1' % size, '-f', 'lavfi',
                                '-i', 'anullsrc=r=48000:cl=stereo', '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                                '-shortest', out], capture_output=True)
            if r.returncode == 0:
                data = base.read(out, 'rb')
            shutil.rmtree(os.path.dirname(out), ignore_errors=True)
        _MP4[size] = data
    return _MP4[size]


def pipeline_build(inp, commit, hits=(), status='ok', config='release', android=None, says=None):
    """A pipeline build of commit, as build.ps1 leaves one: <root>/builds/<slug>/<sha8>/Windows/ (the player the
    recordings are made with) and build_info.json (godot-build/1). A mobile game's build says its platform and its
    Android step (android: 'ok' with Android/KilnRun.apk, 'skipped' without the toolchain); says: another platform
    than the game's, as (platform, orientation)."""
    d = os.path.join(inp['root'], 'builds', SLUG, commit[:8])
    base.write(d, 'Windows/KilnRun.exe', b'MZ' + b'\0' * 30)
    info = {'schema': 'godot-build/1', 'game': SLUG, 'project': 'KilnRun', 'commit': commit, 'short_sha': commit[:8],
            'status': status, 'config': config, 'autoplay_version': 1, 'leak_scan': {'scanned': 'Windows\\', 'hits': list(hits)}}
    o = inp['orientation']
    info['platform'], info['orientation'] = says or (('mobile', o) if o else ('desktop', None))
    if android == 'ok':
        base.write(d, 'Android/KilnRun.apk', APK)
        info['android'] = {'status': 'ok', 'reason': None, 'apk': 'Android\\KilnRun.apk', 'bytes': len(APK), 'package': 'com.kilnrun.game',
                           'min_sdk': 26, 'target_sdk': 34, 'abis': ['arm64-v8a']}
    elif android:
        info['android'] = {'status': android, 'reason': 'no Android toolchain on this machine', 'apk': None}
    base.write(d, 'build_info.json', json.dumps(info))
    return d


def bundle(inp, commit, scenario, stamp, status='ok', result='win', marker=None, notes=None, held='game'):
    """A recording as record.ps1 leaves one: <root>/recordings/<slug>/<run id>/ with metadata.json, validation.json,
    gameplay.mp4 and eight stills (also in recordings/<slug>/_stills/), made at the game's size (held: another
    orientation than the game's, None for a desktop recording). Returns the run id."""
    held = inp['orientation'] if held == 'game' else held
    width, height = SIZES[held]
    run_id = f'{SLUG}_S{scenario}_{stamp}_s7'
    d = os.path.join(inp['root'], 'recordings', SLUG, run_id)
    base.write(d, 'metadata.json', json.dumps({
        'schema': 'godot-autoplay-bundle/v1', 'run_id': run_id, 'game': SLUG, 'scenario': scenario, 'scenario_name': f'Kiln {scenario}',
        'result': result, 'capture_notes': notes, 'status': status, 'platform': 'mobile' if held else 'desktop', 'orientation': held,
        'video': {'width': width, 'height': height, 'fps': 60},
        'build': {'commit': commit, 'short_sha': commit[:8], 'config': 'release',
                  'path': f'C:\\Users\\{ACCOUNT}\\GodotWork\\builds\\{SLUG}\\{commit[:8]}'},
        'gameplay_mp4': {'file': 'gameplay.mp4', 'duration_s': 21.5, 'audio_offset_s': 0.25, 'error': None}}))
    base.write(d, 'validation.json', json.dumps({'status': status, 'problems': [], 'checks': {'video': {'duration_s': 21.5}}}))
    base.write(d, 'gameplay.mp4', gameplay_mp4((width, height)))
    for i in range(1, 9):
        still = b'\xff\xd8\xff\xe0' + bytes([scenario, i]) * 40
        base.write(d, f'stills/{i:02d}.jpg', still)
        base.write(os.path.join(inp['root'], 'recordings', SLUG, '_stills'), f'{run_id}_{i:02d}.jpg', still)
    if marker:
        base.write(d, marker, 'excluded\n')
    return run_id


def record(inp):
    """A valid recording of scenario 1 of the game's head (after a test's own commit: of the new release commit)."""
    return bundle(inp, base.git(inp['repo'], 'rev-parse', 'HEAD'), 1, '20990101-000100')


def replay(inp, commit, passed=False, ready=True):
    """The creation replay's package of commit, as godot_replay.py release leaves it: <out>/_replay/<slug>/<sha8>/ with
    ReplayScripts/ (unscrubbed) and READY."""
    d = os.path.join(inp['root'], 'deliverables', '_replay', SLUG, commit[:8])
    rs = os.path.join(d, 'ReplayScripts')
    base.write(rs, 'Verification/report.json', json.dumps({
        'schema': 'godot-replay.verification/v1', 'game': SLUG, 'final_commit': commit, 'time': '2026-11-10T00:00:00+00:00',
        'files': {'identical': 3, 'differs': ['game/kiln.gd'], 'missing': [], 'extra': []}, 'structure': {'total': 3}, 'runs': {},
        'windows': [{'window': 1, 'commit': commit}],
        'verdict': {'pass': passed, 'criteria': [{'id': 'files', 'text': 'every tracked file byte-identical',
                                                  'result': '3 identical, 1 differs', 'pass': passed}],
                    'exclusions': [{'id': 'uid', 'what': 'uid strings the engine writes at random', 'count': 2, 'items': []}]}}, indent=1))
    base.write(rs, 'Verification/report.md', f'# Replay verification\n\n## Verdict: {"PASS" if passed else "FAIL"}\n')
    base.write(rs, 'README.md', '# ReplayScripts: creation replay of kiln-run\n')
    base.write(rs, 'ledger.json', json.dumps({'final': commit, 'note': f'replayed in C:\\Users\\{ACCOUNT}\\GodotWork\\godot-replay\\{SLUG}'}))
    base.write(rs, 'godot_replay.py', 'print("replay")\n')
    base.write(rs, '__pycache__/godot_replay.cpython-312.pyc', b'\0\0pyc')
    if ready:
        base.write(d, 'READY', '2026-11-10T00:00:00+00:00\n')
    return d


def manifest_of(path):
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read(f'{SLUG}/manifest.json'))


def commit(repo, files, message):
    """Write files ({repo path: text or bytes}) and commit them, by the fixture's dev_1."""
    for rel, data in files.items():
        base.write(repo, rel, data)
    base.git(repo, 'add', '-A')
    base.git(repo, 'commit', '-q', '-m', message)
    return base.git(repo, 'rev-parse', 'HEAD')


@unittest.skipUnless(base.HAS_LFS, 'git-lfs is not installed')
class Package(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='ggfp')
        cls.inp = make_inputs(cls.tmp)
        cls.res = run(cls.inp)
        cls.zip = os.path.join(cls.inp['repo'], 'Dataset.pending.zip')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, onerror=base.onerror)

    def members(self):
        with zipfile.ZipFile(self.zip) as z:
            return {n[len(SLUG) + 1:]: z.read(n) for n in z.namelist()}

    def test_writes_a_valid_pending_zip(self):
        self.assertEqual(self.res.returncode, 0, self.res.stdout + self.res.stderr)
        self.assertTrue(os.path.isfile(self.zip))
        rep = vg.Report()
        vg.check_dataset(rep, self.zip, 'dataset')
        self.assertEqual(base.errors(rep), [])
        m = json.loads(self.members()['manifest.json'])
        self.assertEqual((m['status'], m['pending'], m['variant'], m['version']), ('pending', ['ReplayScripts'], 'full', '1.0'))
        self.assertEqual(m['build']['exe'], 'Build/KilnRun.exe')
        self.assertEqual((m['platform'], m['orientation']), ('desktop', None))   # no Platform.json: a desktop game
        self.assertEqual(m['tasks']['names'], sorted(f'{SLUG}-{n}' for n in base.TASKS))

    def test_entries(self):
        names = set(self.members())
        for want in ('README.md', 'git.log', 'workflow.jsonl', 'Brief/brief.md', 'Brief/design.md', f'History/{SLUG}.bundle',
                     'History/sessions/messages.jsonl', 'History/sessions/actions.jsonl', f'Tasks/{SLUG}-fix-hero-hud/task.json',
                     f'Tasks/{SLUG}-fix-hero-hud/grader.json', 'Tasks/README.md', 'GodotProject/project.godot',
                     'GodotProject/Docs/Notes.md', 'Screenshots/kiln.jpg', 'Build/KilnRun.exe', 'Build/KilnRun.pck',
                     f'Gameplay/{SLUG}_S1.mp4'):
            self.assertIn(want, names)
        self.assertFalse([n for n in names if n.startswith(('ReplayScripts/', 'GodotProject/.godot/', 'GodotProject/Dataset/'))])
        # an LFS file of the project arrives as its content, and as its object in the history
        self.assertTrue(self.members()['GodotProject/Docs/screenshots/kiln.jpg'].startswith(b'\xff\xd8\xff'))
        self.assertTrue([n for n in names if n.startswith('History/lfs/objects/')])

    def test_no_name_is_left_in_text(self):
        for name, data in self.members().items():
            if name.endswith('.bundle') or name.startswith('History/lfs/objects/') or b'\0' in data[:8000]:
                continue
            hit = BANNED.search(data.decode('utf-8', 'replace'))
            self.assertIsNone(hit, f'{name}: {hit and hit.group(0)}')
        notes = self.members()['GodotProject/Docs/Notes.md'].decode()
        self.assertIn('C:\\Users\\dev\\GodotWork with studio-tools and agent-tool', notes)
        self.assertIn('The Model run went well; libopus stays.', notes)
        self.assertIn('cd C:UsersdevGodotWorkgames failed', notes)   # a path whose separators a shell dropped
        self.assertIn('assets/art/Keeper@Walk.fbx', notes)           # a clip's file name is no e-mail address
        tiles = json.loads(self.members()['GodotProject/Docs/data/tiles.json'])
        self.assertEqual(tiles['tiles'], 'ab12' * 75)                  # the game's data stays as committed

    def test_history_is_rewritten(self):
        m = json.loads(self.members()['manifest.json'])
        h = m['history']
        self.assertEqual(sorted(h['refs']), ['refs/heads/main', f'refs/heads/starts/{SLUG}-fix-hero-hud', 'refs/heads/starts/made-elsewhere'])
        self.assertNotEqual(m['commit'], self.inp['head'])
        work = os.path.join(self.tmp, 'restored.git')
        with open(os.path.join(self.tmp, 'h.bundle'), 'wb') as f:
            f.write(self.members()[h['bundle']])
        subprocess.run(['git', 'clone', '-q', '--bare', '--mirror', os.path.join(self.tmp, 'h.bundle'), work], check=True, capture_output=True)
        log = base.git(work, 'log', '--all', '--format=%an|%ae|%cn|%ce|%B')
        self.assertNotRegex(log, r'(?i)jane|tester|claude|anthropic')
        self.assertRegex(log, r'dev_\d+\|dev_\d+@example\.invalid')
        self.assertEqual(base.git(work, 'rev-parse', 'refs/heads/main'), m['commit'])
        self.assertEqual(base.git(work, 'for-each-ref', '--format=%(refname)').split(), sorted(h['refs']))   # no side branch
        self.assertEqual(base.git(work, 'symbolic-ref', 'HEAD'), 'refs/heads/main')
        self.assertEqual(int(base.git(work, 'rev-list', '--all', '--count')), h['commits'])
        # the task's seeds name commits of the delivered history
        t = json.loads(self.members()[f'Tasks/{SLUG}-fix-hero-hud/task.json'])
        g = json.loads(self.members()[f'Tasks/{SLUG}-fix-hero-hud/grader.json'])
        for c in (t['seed']['commit'], g['seed']['reference']):
            self.assertEqual(base.git(work, 'cat-file', '-t', c), 'commit')
        self.assertNotIn('reference', t['seed'])
        self.assertEqual(t['seed']['history'], 'dataset')   # the seed names commits of the delivered history
        self.assertNotIn('milestones', t)
        self.assertTrue(self.members()['git.log'].decode().startswith('GIT-LOG 1\n'))
        self.assertIn(f'commit {m["commit"]}\n', self.members()['git.log'].decode())

    def test_sessions(self):
        mem = self.members()
        msgs = [json.loads(l) for l in mem['History/sessions/messages.jsonl'].decode().splitlines()]
        acts = [json.loads(l) for l in mem['History/sessions/actions.jsonl'].decode().splitlines()]
        # rows after the release commit and the packaging session are left out; ids are numbered the same in both files
        self.assertEqual([(r['session_id'], r['role']) for r in msgs],
                         [('session_01', 'user'), ('session_01', 'assistant'), ('session_01', 'thinking'), ('session_01', 'thinking'),
                          ('session_02', 'user')])
        # a reasoning summary is scrubbed like a reply; one saved without text keeps its mark
        self.assertEqual(msgs[2]['text'], 'Agent should mail <redacted-email> about the hero.')
        self.assertEqual((msgs[3]['text'], msgs[3]['redacted']), ('', True))
        self.assertEqual([(r['session_id'], r['tool']) for r in acts],
                         [('session_01', 'Bash'), ('session_02', 'apply_patch'), ('session_02', 'Bash'), ('session_02', 'Bash')])
        # a whole tool result is delivered whole and scrubbed to its end; a cut one keeps its marks
        self.assertEqual(acts[2]['response'], 'compiling\n' * 3000 + 'saved to C:\\Users\\dev\\GodotWork\\out.txt for <redacted-email>')
        self.assertEqual((acts[3]['response_truncated'], acts[3]['response_chars']), (True, 2000000))
        self.assertEqual(msgs[0]['text'], 'Keep the hero on the ground. Ask <redacted-email> if Studio agrees.')
        self.assertEqual(msgs[1]['text'], 'Done by Agent; Provider was not used.')
        self.assertEqual(msgs[1]['model'], 'agent-model')
        self.assertEqual(acts[0]['input']['session_id'], 'session')            # a session id inside a tool's input
        self.assertEqual(acts[0]['input']['cut'], 'C:\\Users\\dev\\AppData\\Local\\Temp\\session')   # a session folder cut short
        self.assertEqual(acts[0]['input']['notes'], 'C:\\Users\\dev\\AppData\\Roaming\\session\\notes\\notes.md')
        self.assertIn('<base64 omitted, 300 bytes', acts[0]['response'])
        self.assertEqual(acts[1]['response'], 'ok: runs/pilot-2c-model-siege/summary.json')   # the model's name as a segment
        m = json.loads(mem['manifest.json'])
        delivered = json.loads(mem[f'Tasks/{SLUG}-fix-hero-hud/grader.json'])['seed']['reference']
        self.assertTrue(acts[0]['response'].startswith(delivered + '\n'))   # a commit id is the delivered history's
        self.assertNotEqual(delivered, self.inp['ref'])
        self.assertEqual(m['history']['sessions'], {'messages': {'file': 'History/sessions/messages.jsonl', 'rows': 5},
                                                    'actions': {'file': 'History/sessions/actions.jsonl', 'rows': 4}})
        # the validator knows the new rows: nothing about roles, and the summaries counted
        rep = vg.Report()
        vg.check_dataset(rep, self.zip, 'dataset')
        said = [msg for _sev, _area, msg in rep.items]
        self.assertFalse([x for x in said if 'roles other than' in x], said)
        self.assertTrue([x for x in said if '2 prompt(s), 1 repl(ies), 2 reasoning summar(ies)' in x], said)
        readme = mem['README.md'].decode()
        self.assertIn('History/sessions/', readme)
        self.assertIn('pending', readme.lower())

    def test_the_readme_of_a_desktop_game(self):
        readme = self.members()['README.md'].decode()
        self.assertRegex(readme, r'- Godot \d+\.\d+(\.\d+)? \(the standard build\) to open the project')
        self.assertIn('- 64-bit Windows 10/11 for the built player.', readme)
        self.assertIn('Run `Build/KilnRun.exe` (no installation), or open `GodotProject/` in Godot', readme)
        self.assertIn('rebuilds the `.godot/` cache', readme)
        self.assertIn('(1920x1080, 60 fps, H.264 and AAC)', readme)
        self.assertNotRegex(readme, r'(?i)android|\bapk\b|touch')
        heads = re.findall(r'(?m)^## (.+)$', readme)
        self.assertEqual(heads, list(PKG.SECTIONS))   # the layout's sections, in its order
        self.assertEqual(heads, PKG.LAYOUT_SPEC['readme']['sections_in_order'])

    def test_repo_dataset_folder(self):
        ds = os.path.join(self.inp['repo'], 'Dataset')
        rep = vg.Report()
        vg.check_dataset(rep, ds, 'dataset')
        self.assertEqual(base.errors(rep), [])
        self.assertEqual(sorted(os.listdir(ds)), ['.gitattributes', 'Brief', 'Gameplay', 'README.md', 'Screenshots', 'git.log',
                                                  'manifest.json', 'workflow.jsonl'])
        self.assertTrue(base.read(os.path.join(ds, '.gitattributes')).startswith('* -text\n'))   # committed byte for byte
        self.assertIsNone(json.loads(base.read(os.path.join(ds, 'manifest.json')))['history'])
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], '.dataset', f'{SLUG}.history.git')))
        self.assertEqual(base.git(self.inp['repo'], 'rev-parse', 'HEAD'), self.inp['head'])   # the game's history is not changed
        self.assertIn('original\tdelivered', base.read(os.path.join(self.inp['repo'], '.dataset', f'{SLUG}.commit-map.tsv')))


@unittest.skipUnless(base.HAS_LFS, 'git-lfs is not installed')
class Complete(unittest.TestCase):
    """A release with the pipeline's build, recordings and the creation replay: Dataset.zip, status complete."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='ggfc')
        inp = cls.inp = make_inputs(cls.tmp, recorded=False)
        head, start = inp['head'], inp['start']
        pipeline_build(inp, head)
        cls.runs = {
            'failed': bundle(inp, head, 1, '20990101-000000', status='failed', marker='FAILED'),
            's1': bundle(inp, head, 1, '20990101-000100', result='lose'),
            's1_later': bundle(inp, head, 1, '20990101-000200'),
            's2': bundle(inp, head, 2, '20990101-000300', result='timeout', notes='Low quality for 60 fps capture'),
            'invalid': bundle(inp, head, 3, '20990101-000400', marker='INVALID'),
            'older': bundle(inp, start, 4, '20990101-000500')}
        replay(inp, head)
        cls.res = run(inp, build=False)   # the player: the pipeline's build of the release commit
        cls.zip = os.path.join(inp['repo'], 'Dataset.zip')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, onerror=base.onerror)

    def members(self):
        with zipfile.ZipFile(self.zip) as z:
            return {n[len(SLUG) + 1:]: z.read(n) for n in z.namelist()}

    def test_a_complete_zip(self):
        self.assertEqual(self.res.returncode, 0, self.res.stdout + self.res.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], 'Dataset.pending.zip')))
        rep = vg.Report()
        vg.check_dataset(rep, self.zip, 'dataset')
        self.assertEqual(base.errors(rep), [])
        m = manifest_of(self.zip)
        self.assertEqual((m['status'], m['pending']), ('complete', []))
        self.assertIn('COMPLETE', self.res.stdout)

    def test_gameplay_from_the_first_valid_run_of_each_scenario(self):
        m, mem = manifest_of(self.zip), self.members()
        self.assertEqual([(s['scenario'], s['source_run'], s['result']) for s in m['scenarios']],
                         [(1, self.runs['s1'], 'lose'), (2, self.runs['s2'], 'timeout')])   # the result never picks a run
        s1 = m['scenarios'][0]
        self.assertEqual((s1['file'], s1['name'], s1['seconds'], s1['audio_offset_s']), (f'Gameplay/{SLUG}_S1.mp4', 'Kiln 1', 21.5, 0.25))
        self.assertNotIn('capture_notes', s1)
        self.assertEqual(m['scenarios'][1]['capture_notes'], 'Low quality for 60 fps capture')
        self.assertEqual(sorted(n for n in mem if n.startswith('Gameplay/')), [f'Gameplay/{SLUG}_S1.mp4', f'Gameplay/{SLUG}_S2.mp4'])
        self.assertEqual(mem[f'Gameplay/{SLUG}_S1.mp4'], gameplay_mp4())
        readme = mem['README.md'].decode()
        self.assertIn(f'| `Gameplay/{SLUG}_S2.mp4` | 2 | Kiln 2 | timeout | 21.5 s |', readme)
        self.assertIn('Recording note, scenario 2: Low quality for 60 fps capture.', readme)
        for k in ('failed', 'invalid', 'older'):   # FAILED, INVALID and a run of another commit are named, never taken
            self.assertIn(f'recording {self.runs[k]} not taken', self.res.stdout)

    def test_replay_scripts_with_a_fail_verdict(self):
        m, mem = manifest_of(self.zip), self.members()
        rv = m['replay_verification']
        self.assertEqual((rv['pass'], rv['report']), (False, 'ReplayScripts/Verification/report.md'))
        self.assertEqual(rv['criteria'], [{'id': 'files', 'text': 'every tracked file byte-identical',
                                           'result': '3 identical, 1 differs', 'pass': False}])
        self.assertEqual(rv['exclusions'], [{'id': 'uid', 'what': 'uid strings the engine writes at random', 'count': 2}])
        report = json.loads(mem['ReplayScripts/Verification/report.json'])
        self.assertEqual(report['final_commit'], m['commit'])   # the replay's commit ids are the delivered history's
        self.assertEqual(report['windows'][0]['commit'], m['commit'])
        ledger = json.loads(mem['ReplayScripts/ledger.json'])
        self.assertEqual(ledger['note'], f'replayed in C:\\Users\\dev\\GodotWork\\godot-replay\\{SLUG}')   # scrubbed like the rest
        self.assertFalse([n for n in mem if '__pycache__' in n])
        readme = mem['README.md'].decode()
        self.assertIn('verified against the release commit: **FAIL**', readme)
        self.assertNotIn('**Pending:**', readme)

    def test_the_pipelines_player(self):
        m = manifest_of(self.zip)
        self.assertEqual(m['build']['commit'], m['commit'])
        self.assertEqual(m['build']['source'], "the pipeline's release build of the release commit (tools/godot-pipeline/build.ps1)")
        self.assertIn('Build/KilnRun.exe', self.members())

    def test_the_audit_beside_the_deliveries(self):
        m = manifest_of(self.zip)
        out = os.path.join(self.inp['root'], 'deliverables', SLUG)
        report = json.loads(base.read(os.path.join(out, f'{SLUG}_{m["commit"][:8]}.scrub-report.json')))
        self.assertEqual((report['schema'], report['delivered_commit'], report['commit']), ('scrub-report/1', m['commit'], self.inp['head']))
        self.assertGreater(report['files_touched_count'], 0)
        self.assertEqual(report['scan']['text_and_path_hits'], 0)
        self.assertIn('username', {r['id'] for r in report['rules']})
        (row,) = [json.loads(l) for l in base.read(os.path.join(out, 'package-log.jsonl')).splitlines()]
        self.assertEqual((row['status'], row['delivered_commit'], row['replay']), ('complete', m['commit'], 'FAIL'))
        self.assertEqual(row['zip'], self.zip)
        self.assertTrue(os.path.isfile(row['audit']['leaks.tsv']))
        self.assertFalse([n for n in self.members() if 'scrub-report' in n or n.endswith('.tsv')])   # never in the delivery

    def test_the_repo_dataset_folder_has_gameplay_and_replay(self):
        ds = os.path.join(self.inp['repo'], 'Dataset')
        rep = vg.Report()
        vg.check_dataset(rep, ds, 'dataset')
        self.assertEqual(base.errors(rep), [])
        self.assertTrue(os.path.isfile(os.path.join(ds, 'Gameplay', f'{SLUG}_S2.mp4')))
        self.assertTrue(os.path.isfile(os.path.join(ds, 'ReplayScripts', 'Verification', 'report.json')))
        self.assertEqual(json.loads(base.read(os.path.join(ds, 'manifest.json')))['status'], 'complete')


@unittest.skipUnless(base.HAS_LFS, 'git-lfs is not installed')
class Products(unittest.TestCase):
    """What the release's build, recordings and replay decide, one case each."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ggfq')
        self.inp = make_inputs(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, onerror=base.onerror)

    def test_without_ready_the_replay_is_pending(self):
        head = self.inp['head']
        bundle(self.inp, head, 1, '20990101-000100')
        replay(self.inp, head, ready=False)   # a replay still being packaged
        r = run(self.inp, '--no-repo-dataset')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('is not finished (no READY)', r.stdout)
        m = manifest_of(os.path.join(self.inp['repo'], 'Dataset.pending.zip'))
        self.assertEqual((m['status'], m['pending'], m['replay_verification']), ('pending', ['ReplayScripts'], None))
        self.assertEqual(len(m['scenarios']), 1)

    def test_a_replay_of_another_commit_refuses(self):
        head = self.inp['head']
        d = replay(self.inp, head)
        rp = os.path.join(d, 'ReplayScripts', 'Verification', 'report.json')
        report = json.loads(base.read(rp))
        report['final_commit'] = self.inp['start']
        base.write(os.path.dirname(rp), 'report.json', json.dumps(report))
        r = run(self.inp, '--dry-run')
        self.assertEqual(r.returncode, 2)
        self.assertIn('not the release commit', r.stdout)

    def test_leak_scan_hits_refuse(self):
        pipeline_build(self.inp, self.inp['head'], hits=[{'file': 'Windows\\KilnRun.exe', 'pattern': 'claude', 'count': 1}])
        r = run(self.inp, '--dry-run', build=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn('leak-scan hit(s) in build_info.json', r.stdout)

    def test_an_earlier_pipeline_build_is_named(self):
        pipeline_build(self.inp, self.inp['start'])   # the release commit has no build of its own
        r = run(self.inp, '--no-repo-dataset', '--no-zip', build=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('commit(s) before the release commit', r.stdout)
        m = json.loads(base.read(os.path.join(self.inp['repo'], '.dataset', SLUG, 'manifest.json')))
        self.assertNotEqual(m['build']['commit'], m['commit'])
        self.assertNotIn(self.inp['start'], json.dumps(m))   # the build's commit by its delivered id
        self.assertIn(f"the pipeline's release build of commit {m['build']['commit'][:12]}", m['build']['source'])

    def test_a_build_outside_the_release_history_refuses(self):
        base.git(self.inp['repo'], 'switch', '-q', '-c', 'side', self.inp['start'])
        side = commit(self.inp['repo'], {'Docs/Side.md': 'side work\n'}, 'Side work')
        base.git(self.inp['repo'], 'switch', '-q', 'main')
        d = pipeline_build(self.inp, side)
        r = run(self.inp, '--dry-run', '--build', d, build=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn('which is not in the history of the release commit', r.stdout)

    @unittest.skipUnless(os.name == 'nt', 'the pipeline lock is a Windows file opened without sharing')
    def test_the_pipelines_lock_refuses(self):
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                    wintypes.HANDLE)
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        builds = os.path.join(self.inp['root'], 'builds')
        base.write(builds, f'_pipeline-{SLUG}.lock.json', json.dumps({'pid': 4242, 'job': f'build {SLUG} 0123abcd', 'since': 'now'}))
        # as common.ps1 Enter-PipelineLock holds it: read and write, no sharing, opened or created
        h = k32.CreateFileW(os.path.join(builds, f'_pipeline-{SLUG}.lock'), 0xC0000000, 0, None, 4, 0x80, None)
        self.assertNotIn(h, (None, ctypes.c_void_p(-1).value))
        try:
            r = run(self.inp, '--dry-run')
        finally:
            k32.CloseHandle(h)
        self.assertEqual(r.returncode, 2)
        self.assertIn(f'the pipeline is working on {SLUG} right now: build {SLUG} 0123abcd (pid 4242', r.stdout)
        self.assertEqual(run(self.inp, '--dry-run').returncode, 0)   # freed: the file alone is no lock

    def test_screenshots_fall_back_to_the_recordings_stills(self):
        repo = self.inp['repo']
        readme = base.read(os.path.join(repo, 'README.md'))
        head = commit(repo, {'README.md': re.sub(r'(?m)^.*(!\[|<img).*\n', '', readme)}, 'The README without images')
        shutil.rmtree(os.path.join(repo, 'Docs', 'screenshots'), onerror=base.onerror)
        head = commit(repo, {}, 'No screenshots folder')
        run_id = bundle(self.inp, head, 1, '20990101-000100')
        r = run(self.inp, '--no-repo-dataset', '--no-zip')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        shots = sorted(os.listdir(os.path.join(repo, '.dataset', SLUG, 'Screenshots')))
        self.assertEqual(shots, [f'{run_id}_{n}.jpg' for n in ('01', '03', '05', '07')])
        self.assertIn('Screenshots/ holds stills of the recordings', r.stdout)

    def test_a_session_build_before_a_content_change_is_named(self):
        # the template's flow commits the build's workflow row after the build; only a later change to the game's
        # content or code means the build is not the release's
        repo, exe = self.inp['repo'], os.path.join(self.inp['build'], 'KilnRun.exe')
        future = int(time.time()) + 100
        os.utime(exe, (future, future))
        env = dict(base.ENV, GIT_COMMITTER_DATE=f'{future + 50} +0000', GIT_AUTHOR_DATE=f'{future + 50} +0000')
        base.write(repo, 'workflow.jsonl', base.read(os.path.join(repo, 'workflow.jsonl')) + '\n')
        subprocess.run(['git', '-C', repo, 'commit', '-qam', 'Record the build row'], check=True, env=env)
        record(self.inp)
        r = run(self.inp, '--dry-run')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn('was built before', r.stdout)
        base.write(repo, 'project.godot', base.read(os.path.join(repo, 'project.godot')) + '; later\n')
        subprocess.run(['git', '-C', repo, 'commit', '-qam', 'Change the game after the build'], check=True, env=env)
        record(self.inp)
        r = run(self.inp, '--dry-run')
        self.assertIn('Build/KilnRun.exe was built before 1 commit(s) that changed the game', r.stdout)

    def test_the_brief_comes_from_the_release_commit(self):
        repo = self.inp['repo']
        commit(repo, {'Brief/brief.md': '# Brief\n\n' + 'The committed brief. ' * 20, 'Brief/design.md': '# Design\n\n' + 'Committed. ' * 30},
               'Add the brief and the design doc')
        record(self.inp)
        base.write(repo, 'Brief/brief.md', '# Brief\n\n' + 'An edit nobody committed. ' * 20)
        r = run(self.inp, '--no-repo-dataset', '--no-zip', brief=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(base.read(os.path.join(repo, '.dataset', SLUG, 'Brief', 'brief.md')).startswith('# Brief\n\nThe committed brief.'))

    def test_lfs_objects_naming_the_account_are_patched_for_delivery(self):
        # an FBX exported from the profile keeps the path; the delivered history points at a patched copy (same length)
        repo = self.inp['repo']
        commit(repo, {'models/hero.fbx': HERO_FBX}, 'Add the hero model')
        record(self.inp)
        r = run(self.inp, '--no-repo-dataset')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with zipfile.ZipFile(os.path.join(repo, 'Dataset.pending.zip')) as z:
            mem = {n[len(SLUG) + 1:]: z.read(n) for n in z.namelist()}
        patched = HERO_FBX.replace(ACCOUNT.encode(), b'user___')
        self.assertEqual(mem['GodotProject/models/hero.fbx'], patched)
        new = hashlib.sha256(patched).hexdigest()
        objs = {n.rsplit('/', 1)[1] for n in mem if n.startswith('History/lfs/objects/')}
        self.assertIn(new, objs)
        self.assertNotIn(hashlib.sha256(HERO_FBX).hexdigest(), objs)
        with open(os.path.join(self.tmp, 'h.bundle'), 'wb') as f:
            f.write(mem[f'History/{SLUG}.bundle'])
        work = os.path.join(self.tmp, 'restored')
        subprocess.run(['git', 'clone', '-q', '--no-checkout', os.path.join(self.tmp, 'h.bundle'), work], check=True, capture_output=True)
        self.assertIn(f'oid sha256:{new}', base.git(work, 'show', 'main:models/hero.fbx'))
        report = json.loads(base.read(os.path.join(repo, '.dataset', f'{SLUG}.scrub-report.json')))
        self.assertEqual((report['history']['lfs_objects_patched'], report['history']['lfs_pointers_swapped']), (1, 1))

    def test_an_lfs_object_naming_the_account_in_its_text(self):
        # outside a path, a whole string or an element nothing can be patched: the scan refuses it, unless the release
        # commit's clean version of the path stands in for it
        repo = self.inp['repo']
        commit(repo, {'models/notes.fbx': b'\0\1made by ' + ACCOUNT.encode() + b' for the kiln\0'}, 'Add the notes model')
        record(self.inp)
        r = run(self.inp, '--no-repo-dataset', '--no-zip')
        self.assertEqual(r.returncode, 2)
        self.assertIn('cannot be patched', r.stdout)
        commit(repo, {'models/notes.fbx': b'\0\1made by someone for the kiln\0'}, 'Clean the notes model')
        record(self.inp)
        self.assertEqual(run(self.inp, '--no-repo-dataset', '--no-zip').returncode, 2)   # the older commit still holds it
        r = run(self.inp, '--no-repo-dataset', '--no-zip', '--lfs-unpatchable-use-head')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_self_check(self):
        for user in (ACCOUNT, 'nora'):   # a long account name and a short one
            r = run(self.inp, '--self-check', env={'USERNAME': user})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('PASS  self-check', r.stdout)
            self.assertNotIn('FAIL', r.stdout)

    def test_rescan(self):
        r = run(self.inp, '--no-repo-dataset')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        zp = os.path.join(self.inp['repo'], 'Dataset.pending.zip')
        r = run(self.inp, '--rescan', zp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('PASS', r.stdout)
        # a name planted in a delivered copy: the rescan finds it
        bad = os.path.join(self.tmp, 'planted.zip')
        with zipfile.ZipFile(zp) as src, zipfile.ZipFile(bad, 'w') as dst:
            for n in src.namelist():
                dst.writestr(n, src.read(n))
            dst.writestr(f'{SLUG}/GodotProject/Docs/Later.md', f'Moved to C:\\Users\\{ACCOUNT}\\Desktop.\n')
        r = run(self.inp, '--rescan', bad)
        self.assertEqual(r.returncode, 2)
        self.assertIn('FAIL', r.stdout)
        hits = base.read(os.path.join(self.inp['root'], 'deliverables', SLUG, f'{SLUG}.rescan-hits.tsv'))
        self.assertIn('GodotProject/Docs/Later.md\ttext', hits)

    def test_scrub_dir(self):
        folder = os.path.join(self.tmp, 'loose')
        base.write(folder, 'notes.md', f'C:\\Users\\{ACCOUNT}\\GodotWork with godot-game-factory and Claude Code.\n')
        base.write(folder, 'data.bin', b'\0\1jtester\0')
        r = run(self.inp, '--scrub-dir', folder)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(base.read(os.path.join(folder, 'notes.md')), 'C:\\Users\\dev\\GodotWork with studio-tools and agent-tool.\n')
        self.assertEqual(base.read(os.path.join(folder, 'data.bin'), 'rb'), b'\0\1jtester\0')   # binaries are never changed
        report = json.loads(base.read(os.path.join(self.inp['root'], 'deliverables', SLUG, f'{SLUG}.scrub-dir.json')))
        self.assertEqual(report['touched'], 1)

    def test_commit_milestone_and_the_release_tag(self):
        repo = self.inp['repo']
        base.git(repo, 'tag', 'milestone/autoplay-1', self.inp['start'])
        base.git(repo, 'tag', 'milestone/autoplay-2', 'HEAD~1')
        base.git(repo, 'tag', 'release/1.0', self.inp['start'])
        bundle(self.inp, base.git(repo, 'rev-parse', 'HEAD~1'), 1, '20990101-000200')   # the milestone's own recording
        r = run(self.inp, '--dry-run', '--commit', 'milestone')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('--commit milestone: milestone/autoplay-2', r.stdout)
        self.assertIn('the tag release/1.0 names', r.stdout)

    def test_the_ignore_fallback(self):
        repo = self.inp['repo']
        text = base.read(os.path.join(repo, '.gitignore'))
        commit(repo, {'.gitignore': '\n'.join(l for l in text.splitlines() if 'Dataset' not in l and '.dataset' not in l) + '\n'},
               'An older .gitignore')
        record(self.inp)
        r = run(self.inp, '--no-repo-dataset')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        exclude = base.read(os.path.join(repo, '.git', 'info', 'exclude'))
        for pat in ('/Dataset.zip', '/Dataset.pending.zip', '/.dataset/'):
            self.assertIn(pat, exclude)
        self.assertEqual(base.git(repo, 'status', '--porcelain'), '')   # the zip and the scratch stay out of git


HERO_FBX = b'Kaydara FBX Binary  \0\x1a\0' + b'\0FileName\0C:\\Users\\' + ACCOUNT.encode() + b'\\Desktop\\hero.blend\0\1\2'


@unittest.skipUnless(base.HAS_LFS, 'git-lfs is not installed')
class Helpers(unittest.TestCase):
    """The pipeline's history tools: export-lfs-history.py, scrub-lfs-history.py, scrub-history.ps1."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ggfh')
        self.inp = make_inputs(self.tmp)
        self.env = dict(base.ENV, GGF_ROOT=self.inp['root'], GGF_CONFIG=os.path.join(self.inp['root'], 'no-config.json'),
                        USERNAME=ACCOUNT)

    def tearDown(self):
        shutil.rmtree(self.tmp, onerror=base.onerror)

    def tool(self, name, *args):
        return subprocess.run([sys.executable, os.path.join(TOOLS, 'godot-pipeline', name), *args], capture_output=True, text=True, env=self.env)

    def test_export_lfs_history(self):
        commit(self.inp['repo'], {'models/hero.fbx': HERO_FBX}, 'Add the hero model')
        out = os.path.join(self.tmp, 'objects')
        r = self.tool('export-lfs-history.py', self.inp['repo'], out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        res = json.loads(r.stdout)
        new = hashlib.sha256(HERO_FBX.replace(ACCOUNT.encode(), b'user___')).hexdigest()
        self.assertEqual((res['patched'], res['map'][hashlib.sha256(HERO_FBX).hexdigest()][0]), (1, new))
        self.assertTrue(os.path.isfile(os.path.join(out, new[:2], new[2:4], new)))

    def test_scrub_lfs_history(self):
        repo = self.inp['repo']
        commit(repo, {'models/hero.fbx': HERO_FBX}, 'Add the hero model')
        r = self.tool('scrub-lfs-history.py', SLUG, '--repo', repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('dry run: nothing changed', r.stdout)
        r = self.tool('scrub-lfs-history.py', SLUG, '--repo', repo, '--apply')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        new = hashlib.sha256(HERO_FBX.replace(ACCOUNT.encode(), b'user___')).hexdigest()
        self.assertIn(f'oid sha256:{new}', base.git(repo, 'show', 'HEAD:models/hero.fbx'))
        self.assertEqual(base.git(repo, 'for-each-ref', 'refs/original/'), '')

    @unittest.skipUnless(os.name == 'nt' and shutil.which('powershell'), 'Windows PowerShell and Git for Windows')
    def test_scrub_history(self):
        repo = self.inp['repo']
        commit(repo, {'Docs/Studio.md': 'Made with godot-game-factory at Superposition.\n'}, 'Docs from the game-factory notes')
        ps = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', os.path.join(TOOLS, 'godot-pipeline', 'scrub-history.ps1'),
              SLUG, '-RepoPath', repo, '-ArchiveDir', os.path.join(self.tmp, 'archive'), '-QuietMinutes', '0']
        r = subprocess.run(ps, capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('dry run: nothing changed', r.stdout)
        r = subprocess.run(ps + ['-Apply'], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('after: text blobs with a name 0', r.stdout)
        self.assertEqual(base.git(repo, 'show', 'HEAD:Docs/Studio.md'), 'Made with studio-tools at Studio.')
        self.assertNotRegex(base.git(repo, 'log', '--all', '--format=%B'), r'(?i)game[-_ ]?factory|superposition')


@unittest.skipUnless(base.HAS_LFS, 'git-lfs is not installed')
class Mobile(unittest.TestCase):
    """A mobile game (Platform.json at the release commit): its platform in the manifest, the APK and no Windows player
    in Build/, Build/ pending while the release has no APK, the videos at the phone's size, the README's wording."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ggfm')

    def tearDown(self):
        shutil.rmtree(self.tmp, onerror=base.onerror)

    def members(self, name):
        with zipfile.ZipFile(os.path.join(self.inp['repo'], name)) as z:
            return {n[len(SLUG) + 1:]: z.read(n) for n in z.namelist()}

    def test_a_mobile_package(self):
        inp = self.inp = make_inputs(self.tmp, orientation='portrait')
        pipeline_build(inp, inp['head'], android='ok')
        replay(inp, inp['head'], passed=True)
        r = run(inp, build=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        mem = self.members('Dataset.zip')
        m = json.loads(mem['manifest.json'])
        self.assertEqual((m['platform'], m['orientation'], m['status'], m['pending']), ('mobile', 'portrait', 'complete', []))
        b = m['build']
        self.assertEqual((b['apk'], b['bytes'], b['package'], b['min_sdk'], b['target_sdk'], b['abis']),
                         ('Build/KilnRun.apk', len(APK), 'com.kilnrun.game', 26, 34, ['arm64-v8a']))
        self.assertNotIn('exe', b)
        self.assertEqual(sorted(n for n in mem if n.startswith('Build/')), ['Build/KilnRun.apk'])   # no Windows player
        self.assertEqual(mem['Build/KilnRun.apk'], APK)
        self.assertEqual(json.loads(mem['GodotProject/Platform.json']), {'platform': 'mobile', 'orientation': 'portrait'})
        self.assertEqual(mem[f'Gameplay/{SLUG}_S1.mp4'], gameplay_mp4((1080, 1920)))
        readme = mem['README.md'].decode()
        for want in ('An Android phone game, held portrait and played by touch.',
                     '- An arm64 Android phone with Android 8.0 (API 26) or later for the built game',
                     'adb install Build/KilnRun.apk', 'Or open `GodotProject/` in Godot',
                     "recorded on a PC with the Mobile renderer at the phone's size and played by touch events (1080x1920, 60 fps",
                     '- `Build/` — the Android release APK (`Build/KilnRun.apk`, package `com.kilnrun.game`'):
            self.assertIn(want, readme)
        self.assertNotRegex(readme, r'Windows 10/11|\.exe')
        self.assertEqual(re.findall(r'(?m)^## (.+)$', readme), PKG.LAYOUT_SPEC['readme']['sections_in_order'])
        ds = json.loads(base.read(os.path.join(inp['repo'], 'Dataset', 'manifest.json')))   # the repo's Dataset/ says it too
        self.assertEqual((ds['platform'], ds['orientation'], ds['build']), ('mobile', 'portrait', None))

    def test_without_an_apk_the_build_is_pending(self):
        # built on a machine without the Android toolchain: everything else is packaged, and one line says how to get the APK
        inp = self.inp = make_inputs(self.tmp, orientation='landscape')
        pipeline_build(inp, inp['head'], android='skipped')
        replay(inp, inp['head'], passed=True)
        r = run(inp, '--no-repo-dataset', build=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(inp['repo'], 'Dataset.zip')))
        (line,) = [l for l in r.stdout.splitlines() if 'machine/get-android.ps1' in l]
        self.assertIn('Build/ stays pending: no Android APK of the release (the Android build was skipped: no Android toolchain on '
                      'this machine). Install the Android toolchain with machine/get-android.ps1, then build again '
                      f'(tools/godot-pipeline/build.ps1 {SLUG} -Force)', line)
        mem = self.members('Dataset.pending.zip')
        m = json.loads(mem['manifest.json'])
        self.assertEqual((m['platform'], m['orientation'], m['status'], m['pending']), ('mobile', 'landscape', 'pending', ['Build']))
        self.assertEqual(sorted(k for k in m['build']), ['commit', 'config', 'source'])
        self.assertFalse([n for n in mem if n.startswith('Build/')])
        self.assertTrue([n for n in mem if n.startswith('ReplayScripts/')])   # the replay is there: Build/ alone is pending
        readme = mem['README.md'].decode()
        self.assertIn('> **Pending:** `Build/` (the Android APK) is not in this delivery yet', readme)
        self.assertIn('The Android APK is pending. Open `GodotProject/` in Godot', readme)
        self.assertIn('(1920x1080, 60 fps', readme)
        self.assertNotIn('adb install', readme)

    def test_a_mobile_game_without_any_build_is_pending_too(self):
        inp = self.inp = make_inputs(self.tmp, orientation='landscape')
        shutil.rmtree(inp['build'])
        r = run(inp, '--dry-run')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('Build/ stays pending: no Android APK of the release (no KilnRun.apk in ', r.stdout)
        self.assertIn('Dataset.pending.zip (pending: ReplayScripts, Build pending)', r.stdout)

    def test_the_sessions_own_apk(self):
        # Scripts/godot.ps1 build -Android: an APK with no build record, so the manifest says its file and size alone
        inp = self.inp = make_inputs(self.tmp, orientation='landscape')
        r = run(inp, '--no-repo-dataset', '--no-zip')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        m = json.loads(base.read(os.path.join(inp['repo'], '.dataset', SLUG, 'manifest.json')))
        self.assertEqual((m['pending'], m['build']['apk'], m['build']['bytes']), (['ReplayScripts'], 'Build/KilnRun.apk', len(APK)))
        self.assertNotIn('package', m['build'])
        self.assertEqual(os.listdir(os.path.join(inp['repo'], '.dataset', SLUG, 'Build')), ['KilnRun.apk'])

    def test_a_build_made_as_another_platform_refuses(self):
        inp = self.inp = make_inputs(self.tmp, orientation='landscape')
        pipeline_build(inp, inp['head'], android='ok', says=('mobile', 'portrait'))
        r = run(inp, '--dry-run', build=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn('was made as mobile portrait, but the game is mobile landscape (build_info.json against Platform.json', r.stdout)

    def test_a_recording_made_as_another_platform_is_not_taken(self):
        inp = self.inp = make_inputs(self.tmp, orientation='portrait', recorded=False)
        run_id = bundle(inp, inp['head'], 1, '20990101-000100', held='landscape')
        r = run(inp, '--dry-run')
        self.assertEqual(r.returncode, 2)   # no video of the release at the game's size: nothing is packaged
        self.assertIn(f'recording {run_id} not taken: made as mobile landscape, but the game is mobile portrait', r.stdout)
        self.assertIn('error: no gameplay video', r.stdout)

    @unittest.skipUnless(FFMPEG and os.path.isfile(FFMPEG), 'ffmpeg is not installed: the videos are not probed')
    def test_the_video_is_probed_at_the_phones_size(self):
        # a bundle that says nothing of its platform: the video itself is measured
        inp = self.inp = make_inputs(self.tmp, orientation='portrait', recorded=False)
        run_id = bundle(inp, inp['head'], 1, '20990101-000100', held='landscape')
        mp = os.path.join(inp['root'], 'recordings', SLUG, run_id, 'metadata.json')
        meta = json.loads(base.read(mp))
        for k in ('platform', 'orientation', 'video'):
            del meta[k]
        base.write(os.path.dirname(mp), 'metadata.json', json.dumps(meta))
        r = run(inp, '--dry-run')
        self.assertEqual(r.returncode, 2)
        self.assertIn(f"recording {run_id} not taken: gameplay.mp4 is not the layout's video (video h264 1920x1080)", r.stdout)
        good = bundle(inp, inp['head'], 1, '20990101-000200')
        r = run(inp, '--dry-run')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f'would take Gameplay/{SLUG}_S1.mp4 from {good}', r.stdout)

    def test_the_sizes_by_platform(self):
        self.assertEqual([PKG.video_size(o) for o in (None, 'landscape', 'portrait')], [(1920, 1080), (1920, 1080), (1080, 1920)])
        self.assertEqual([PKG.platform_words(o) for o in (None, 'landscape', 'portrait')], ['desktop', 'mobile landscape', 'mobile portrait'])
        self.assertIsNone(PKG.platform_problem({}, 'portrait'))   # a record that says nothing
        self.assertIsNone(PKG.platform_problem({'platform': 'desktop', 'orientation': None}, None))
        self.assertIn('made as desktop', PKG.platform_problem({'platform': 'desktop'}, 'landscape'))

    def test_a_platform_file_that_says_anything_else_refuses(self):
        inp = self.inp = make_inputs(self.tmp)
        commit(inp['repo'], {vg.PLATFORM_FILE: '{"platform": "mobile", "orientation": "sideways"}\n'}, 'A broken platform file')
        record(inp)
        r = run(inp, '--dry-run')
        self.assertEqual(r.returncode, 2)   # never read as a desktop game
        self.assertIn(f'{vg.PLATFORM_FILE} must be', r.stderr)

    def test_the_platform_is_the_release_commits(self):
        # the platform is read from the release commit, never from the working tree: an older commit of a game is
        # packaged as what it was then
        inp = self.inp = make_inputs(self.tmp)
        self.assertIsNone(PKG.platform_at(inp['repo'], inp['head']))
        for name, text in zip(('project.godot', 'export_presets.cfg'), base.mobile_files('portrait')):
            base.write(inp['repo'], name, text)
        later = commit(inp['repo'], {vg.PLATFORM_FILE: '{"platform":"mobile","orientation":"portrait"}\n'}, 'Go mobile')
        self.assertEqual(PKG.platform_at(inp['repo'], later), 'portrait')
        r = run(inp, '--dry-run', '--commit', inp['head'])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f'{SLUG} (desktop): commit', r.stdout)

    def test_a_platform_file_that_is_not_committed_refuses(self):
        # rule `mobile` reads the checkout: a Platform.json the game never committed is no way to make it a mobile game
        inp = self.inp = make_inputs(self.tmp)
        base.write(inp['repo'], vg.PLATFORM_FILE, '{"platform":"mobile","orientation":"portrait"}\n')
        r = run(inp, '--dry-run')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(f'mobile: {vg.PLATFORM_FILE} is not committed', r.stderr)


def box(kind, payload):
    return (8 + len(payload)).to_bytes(4, 'big') + kind + payload


def mp4(payload, handler=b'vide', meta=b''):
    """A minimal MP4: ftyp, moov with one track (its hdlr) and a udta of meta, mdat holding payload."""
    hdlr = box(b'hdlr', b'\0' * 8 + handler + b'\0' * 12 + b'track\0')
    moov = box(b'moov', box(b'trak', box(b'mdia', hdlr)) + (box(b'udta', meta) if meta else b''))
    return box(b'ftyp', b'isom\0\0\0\0isom') + moov + box(b'mdat', payload)


def ebml(eid, payload):
    n = len(payload)
    return eid + (bytes([0x80 | n]) if n < 127 else bytes([0x40 | (n >> 8), n & 0xFF])) + payload


def mkv(frame, tags=b''):
    """A minimal Matroska: one video track, one cluster with a SimpleBlock of frame data, and a Tags element of tags."""
    head = ebml(b'\x1a\x45\xdf\xa3', ebml(b'\x42\x82', b'matroska'))
    tracks = ebml(b'\x16\x54\xae\x6b', ebml(b'\xae', ebml(b'\xd7', b'\x01') + ebml(b'\x83', b'\x01')))
    cluster = ebml(b'\x1f\x43\xb6\x75', ebml(b'\xe7', b'\x00') + ebml(b'\xa3', b'\x81\x00\x00\x80' + frame))
    return head + ebml(b'\x18\x53\x80\x67', tracks + cluster + (ebml(b'\x12\x54\xc3\x67', tags) if tags else b''))


class BigRows(unittest.TestCase):
    """A row file too large to read whole (History/sessions/actions.jsonl holds every tool call's whole output) is
    scrubbed, given the delivered commit ids and scanned a row at a time, with the result reading it whole gives; it is
    never left out as other text of that size is."""
    USER = 'nora'
    OLD, NEW = 'a1' * 20, 'b2' * 20

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ggfr')
        self.limit, PKG.BIG_TEXT = PKG.BIG_TEXT, 4000
        self.rel = 'History/sessions/actions.jsonl'
        self.text = ''.join(row(schema='agent-action/v0', time='2026-01-01T00:00:00+00:00', session_id='session_01', event='PostToolUse', tool='Bash',
                                tool_use_id=f't{i}', response='building\n' * 80 + f'caf\u00e9 {self.OLD} C:\\Users\\{self.USER}\\GodotWork\\log{i}.txt '
                                f'nora.q@corp.example by Claude ' + 'QUJD' * 100) + '\n' for i in range(8))
        self.assertGreater(len(self.text.encode()), PKG.BIG_TEXT)
        self.rules = PKG.build_rules(self.USER, 'NORA-PC', set(), [])

    def tearDown(self):
        PKG.BIG_TEXT = self.limit
        shutil.rmtree(self.tmp, onerror=base.onerror)

    def test_scrubbed_and_remapped_as_a_whole_read_would(self):
        base.write(self.tmp, self.rel, self.text)
        base.write(self.tmp, 'Docs/big.txt', f'by {self.USER}\n' * 600)   # other text of that size: left to the scan, as before
        whole = PKG.remap_text(PKG.apply_rules(self.text.encode().decode('latin-1'), self.rules, True, True), {self.OLD: self.NEW})
        counts, touched = {}, []
        PKG.scrub_tree(self.tmp, self.rules, counts, touched)
        self.assertEqual(touched, [self.rel])
        self.assertEqual(PKG.remap_tree(self.tmp, {self.OLD: self.NEW}), 1)
        got = base.read(os.path.join(self.tmp, *self.rel.split('/')))
        self.assertEqual(got, whole.encode('latin-1').decode())
        rows = [json.loads(l) for l in got.splitlines()]
        self.assertEqual(len(rows), 8)
        for i, r in enumerate(rows):
            self.assertEqual(r['response'], 'building\n' * 80 + f'caf\u00e9 {self.NEW} C:\\Users\\dev\\GodotWork\\log{i}.txt <redacted-email> by Agent '
                             + r['response'][r['response'].index('<base64 omitted'):])
            self.assertRegex(r['response'], r'<base64 omitted, 300 bytes, sha256 [0-9a-f]{16}>$')
        self.assertGreaterEqual(counts.get('username', 0), 8)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, *self.rel.split('/')) + '.rows-tmp'))

    def test_scanned_a_row_at_a_time(self):
        base.write(self.tmp, self.rel, self.text)
        out = PKG.scan_tree(self.tmp, PKG.enforced_pattern(self.USER, []), PKG.binary_needles(self.USER, [], []), self.USER)
        lines = sorted({h[2] for h in out['hits'] if h[0] == self.rel and h[1] == 'text'})
        self.assertEqual(lines, [1, 2, 3, 4, 5, 6, 7])   # every row refuses (20 hits listed a file: three a row)
        self.assertFalse([b for b in out['binary'] if b[0] == self.rel])   # read as text, not as bytes
        counts, touched = {}, []
        PKG.scrub_tree(self.tmp, self.rules, counts, touched)
        out = PKG.scan_tree(self.tmp, PKG.enforced_pattern(self.USER, []), PKG.binary_needles(self.USER, [], []), self.USER)
        self.assertEqual([h for h in out['hits'] if h[0] == self.rel], [])


class Scan(unittest.TestCase):
    """The scan's rules on files made here: what refuses, what is listed and what is allowed."""
    USER = 'nora'

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ggfs')
        self.needles = PKG.binary_needles(self.USER, [('Jane Tester', 'dev_01'), ('jtester42', 'dev_01')], ['jane.tester@corp.example'])

    def tearDown(self):
        shutil.rmtree(self.tmp, onerror=base.onerror)

    def scan(self, files, reviewed=None):
        for rel, data in files.items():
            base.write(self.tmp, rel, data)
        return PKG.scan_tree(self.tmp, PKG.enforced_pattern(self.USER, []), self.needles, self.USER, reviewed)

    def kinds(self, out, rel):
        return sorted({b[6] for b in out['binary'] if b[0] == rel} | {a[1] for a in out['allowed'] if a[0] == rel})

    def test_the_opus_codec_and_the_models_name(self):
        rnd = __import__('random').Random(7)
        noise = lambda: bytes(rnd.randrange(256) for _ in range(600))   # noqa: E731
        out = self.scan({'Build/a.dll': b'\0opus_decode\0SpcSpOpusInfo\0libopus.dll\0audio/opus\0',   # the codec's own forms
                         'Build/b.dat': noise() + b'\xf3\xf2k3opusSe\xa0\x12' + noise(),               # compressed bytes spell it
                         'Build/c.dll': b'\0trained on claude-opus-4 weights\0'})                     # the model's name
        self.assertEqual(self.kinds(out, 'Build/a.dll'), ['allowed-codec'])
        self.assertEqual(self.kinds(out, 'Build/b.dat'), ['allowed-entropy'])
        self.assertEqual(self.kinds(out, 'Build/c.dll'), ['binary'])

    def test_media_payloads_allow_short_terms_their_metadata_does_not(self):
        frame = b'\x00\x01' + b'xx Claude xx' + b'\x02'
        out = self.scan({'Gameplay/kiln-run_S1.mp4': mp4(frame), 'Gameplay/kiln-run_S2.mp4': mp4(b'\0\1\2', meta=b'\xa9cmt Made by Claude now'),
                         'GodotProject/assets/a.wav': b'RIFF\x30\0\0\0WAVEdata\x10\0\0\0' + frame[:16],
                         'GodotProject/assets/b.mkv': mkv(frame), 'GodotProject/assets/c.mkv': mkv(b'\0\1\2', tags=b'by Claude here!')})
        self.assertEqual(self.kinds(out, 'Gameplay/kiln-run_S1.mp4'), ['allowed-stream'])
        self.assertEqual(self.kinds(out, 'Gameplay/kiln-run_S2.mp4'), ['binary'])
        self.assertEqual(self.kinds(out, 'GodotProject/assets/a.wav'), ['allowed-stream'])
        self.assertEqual(self.kinds(out, 'GodotProject/assets/b.mkv'), ['allowed-stream'])
        self.assertEqual(self.kinds(out, 'GodotProject/assets/c.mkv'), ['binary'])
        # an mp4 with a track that is neither video nor audio (subtitles) gets no allowance
        out = self.scan({'Gameplay/kiln-run_S3.mp4': mp4(frame, handler=b'sbtl')})
        self.assertEqual(self.kinds(out, 'Gameplay/kiln-run_S3.mp4'), ['binary'])

    def test_a_short_account_name(self):
        out = self.scan({'Build/locale.bin': b'\0\1zh_nora\0\1',        # a locale id
                         'Build/cstring.bin': b'\x01\x02\0Nora\0\x03',  # a whole C string, however short
                         'Build/random.bin': b'\x01\x02\x7fNora\x03',   # a few letters among random bytes: listed only
                         'Build/word.bin': b'\0Manor.Minoratoria\0'})    # inside longer words: no hit
        self.assertEqual(self.kinds(out, 'Build/locale.bin'), ['allowed-locale'])
        self.assertEqual(self.kinds(out, 'Build/cstring.bin'), ['binary'])
        self.assertEqual(self.kinds(out, 'Build/random.bin'), ['binary-info'])
        self.assertEqual(self.kinds(out, 'Build/word.bin'), [])

    def test_the_historys_people_and_addresses(self):
        out = self.scan({'GodotProject/assets/a.png': b'\x89PNG\r\n\x1a\n\0tEXtAuthor\0jane.tester@corp.example\0',
                         'GodotProject/assets/b.fbx': b'\0Kaydara\0Creator\0Jane Tester\0',
                         'GodotProject/assets/c.fbx': b'\0Creator\0Jane Testers Guild\0',      # a longer name: not theirs
                         'Build/KilnRun.exe': b'\0contact vrpn@cs.unc.edu for help\0'})
        self.assertEqual(self.kinds(out, 'GodotProject/assets/a.png'), ['binary'])
        self.assertEqual(self.kinds(out, 'GodotProject/assets/b.fbx'), ['binary'])
        self.assertEqual(self.kinds(out, 'GodotProject/assets/c.fbx'), [])
        self.assertEqual([(e[0], e[2]) for e in out['emails']], [('Build/KilnRun.exe', 'vrpn@cs.unc.edu')])   # listed only

    def test_a_reviewed_hit(self):
        data = b'\x10\x11\x12' + b'random claudeXYZ bytes' + b'\x13'
        out = self.scan({'Build/x.bin': data})
        (hit,) = [b for b in out['binary'] if b[6] == 'binary']
        reviewed = {(hashlib.sha256(data).hexdigest(), hit[1]): hit[5]}
        out = self.scan({'Build/x.bin': data}, reviewed)
        self.assertEqual(self.kinds(out, 'Build/x.bin'), ['allowed-reviewed'])
        out = self.scan({'Build/x.bin': data + b'\0'}, reviewed)   # another version of the file: refuses again
        self.assertEqual(self.kinds(out, 'Build/x.bin'), ['binary'])

    def test_text_allowances_and_other_profiles(self):
        out = self.scan({'History/sessions/actions.jsonl': '{"r": "zh_nora", "b": "\\\\x86\\\\x12\\\\x99Nora\\\\x1c\\\\x00\\\\x01"}\n',
                         'GodotProject/Docs/Notes.md': 'Copied from C:\\Users\\bob\\Desktop and /home/alice/art; see C:\\Users\\dev\\x.\n'})
        self.assertEqual(out['hits'], [])
        self.assertEqual(sorted(a[1] for a in out['allowed']), ['allowed-escaped-bytes', 'allowed-locale'])
        self.assertEqual(sorted(l[2] for l in out['leaks']), ['/home/alice', 'C:\\Users\\bob'])


@unittest.skipUnless(base.HAS_LFS, 'git-lfs is not installed')
class Refusals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ggfr')
        self.inp = make_inputs(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, onerror=base.onerror)

    def test_no_build(self):
        shutil.rmtree(self.inp['build'])
        r = run(self.inp)
        self.assertEqual(r.returncode, 2)
        self.assertIn('no player build', r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], 'Dataset.pending.zip')))

    def test_only_this_games_player(self):
        # an export is named after the project (the release commit's export preset): another project's player refuses
        os.rename(os.path.join(self.inp['build'], 'KilnRun.exe'), os.path.join(self.inp['build'], 'LampKeeper.exe'))
        r = run(self.inp, '--dry-run')
        self.assertEqual(r.returncode, 2)
        self.assertIn('LampKeeper.exe is a player of "LampKeeper", not of this game ("KilnRun" at the commit)', r.stdout)
        base.write(self.inp['build'], 'KilnRun.exe', b'MZ' + b'\0' * 30)   # this game's player beside it is the one taken
        self.assertEqual(run(self.inp, '--dry-run').returncode, 0)

    def test_no_tasks(self):
        base.git(self.inp['repo'], 'update-ref', '-d', 'refs/heads/tasks')
        r = run(self.inp)
        self.assertEqual(r.returncode, 2)
        self.assertIn('no tasks', r.stdout)

    def test_no_gameplay_video(self):
        # a game without a gameplay video is rejected at upload: Gameplay/ is never pending
        shutil.rmtree(os.path.join(self.inp['root'], 'recordings'), onerror=base.onerror)
        for extra in ((), ('--dry-run',)):
            r = run(self.inp, *extra)
            self.assertEqual(r.returncode, 2)
            self.assertIn('error: no gameplay video: no valid recording of the release commit', r.stdout)
            self.assertIn('a game without a gameplay video is rejected at upload. Record a scenario of the release commit', r.stdout)
            self.assertIn('then package again', r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], 'Dataset.pending.zip')))
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], '.dataset')))
        # a recording of another commit is no video of the release
        bundle(self.inp, self.inp['start'], 1, '20990101-000100')
        r = run(self.inp, '--dry-run')
        self.assertEqual(r.returncode, 2)
        self.assertIn('error: no gameplay video', r.stdout)

    def test_fewer_than_five_tasks(self):
        tasks = base.game_tasks(self.inp['start'], self.inp['ref'])
        del tasks[f'{SLUG}-{base.TASKS[-1]}']
        base.set_tasks(self.inp['repo'], tasks)
        r = run(self.inp, '--dry-run')
        self.assertEqual(r.returncode, 2)
        self.assertIn('error: 4 task(s) on tasks: a game with fewer than 5 tasks is rejected', r.stdout)

    def test_fewer_than_four_hard_tasks(self):
        # the delivery's own check refuses it: nothing is zipped
        tasks = base.game_tasks(self.inp['start'], self.inp['ref'], difficulty='medium')
        del tasks[f'{SLUG}-{base.TASKS[1]}']['difficulty']
        base.set_tasks(self.inp['repo'], tasks)
        r = run(self.inp, '--no-repo-dataset')
        self.assertEqual(r.returncode, 2)
        self.assertIn("3 hard task(s): a game needs at least 4 hard tasks", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], 'Dataset.pending.zip')))

    def test_dry_run_writes_nothing(self):
        r = run(self.inp, '--dry-run')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], '.dataset')))
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], 'Dataset.pending.zip')))

    def test_one_run_per_game(self):
        # a run holds <out>/<slug>/.package.lock: a second one at the same time is refused before it touches the scratch
        lock = os.path.join(self.inp['root'], 'deliverables', SLUG, '.package.lock')
        os.makedirs(os.path.dirname(lock))
        with open(lock, 'a+b') as f:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            r = run(self.inp, '--no-repo-dataset')
        self.assertEqual(r.returncode, 2)
        self.assertIn('another package-dataset run of this game', r.stderr)
        r = run(self.inp, '--no-repo-dataset')   # the lock freed
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        maps = [n for n in os.listdir(os.path.dirname(lock)) if n.endswith('.commit-map.tsv')]
        self.assertEqual(len(maps), 1)   # kept beside the deliveries: <slug>_<delivered head 8>.commit-map.tsv

    def test_a_second_run(self):
        # git writes its pack files read-only: the first run's scratch must not stop the second (on Windows it did)
        for _ in range(2):
            r = run(self.inp, '--no-repo-dataset')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.inp['repo'], '.dataset', f'{SLUG}.history.git')))

    def test_the_committed_dataset_folder_checks_out_unchanged(self):
        # a session commits Dataset/, and a checkout with core.autocrlf (Git for Windows' default) must give back the bytes
        # manifest.json lists
        r = run(self.inp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        repo = self.inp['repo']
        base.git(repo, 'config', 'core.autocrlf', 'true')
        base.git(repo, 'add', 'Dataset')
        base.git(repo, 'commit', '-q', '-m', 'Commit the dataset folder')
        shutil.rmtree(os.path.join(repo, 'Dataset'), onerror=base.onerror)
        base.git(repo, 'checkout', '--', 'Dataset')
        rep = vg.Report()
        vg.check_dataset(rep, os.path.join(repo, 'Dataset'), 'dataset')
        self.assertEqual(base.errors(rep), [])

    def test_a_name_in_a_binary_refuses_unless_lenient(self):
        base.write(self.inp['build'], 'KilnRun.pck', b'GDPC\0\1\2' + b'built by godot-game-factory tools' + b'\0\1')
        r = run(self.inp)
        self.assertEqual(r.returncode, 2)
        self.assertIn('name(s) left', r.stderr)
        r = run(self.inp, '--lenient-binaries')   # listed only: to review a refusal
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('binary file(s)', r.stdout)
        hits = base.read(os.path.join(self.inp['repo'], '.dataset', f'{SLUG}.binary-hits.tsv'))
        self.assertIn('Build/KilnRun.pck', hits)

    def test_a_short_account_name_inside_a_longer_word_is_no_hit(self):
        # the engine's own files spell a short account name inside longer words and identifiers, in any case; a path
        # with the name in a binary is a hit
        base.write(self.inp['build'], 'words.dll', b'\0\1' + b'.ManorAccess.Minoratoria.' * 3 + b'\0')
        r = run(self.inp, env={'USERNAME': 'nora'})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        base.write(self.inp['build'], 'KilnRun.pck', b'GDPC\0\1\2' + b'C:\\Users\\Nora\\Desktop\\kiln.fbx' + b'\0\1')
        r = run(self.inp, env={'USERNAME': 'nora'})
        self.assertEqual(r.returncode, 2)
        self.assertIn('KilnRun.pck', base.read(os.path.join(self.inp['repo'], '.dataset', f'{SLUG}.refused-hits.tsv')))

    def test_a_name_on_a_start_branch_alone_refuses(self):
        # git.log shows main's history only; a start branch's own commits are in the bundle alone, and are scanned there
        repo = self.inp['repo']
        base.git(repo, 'switch', '-q', f'starts/{SLUG}-fix-hero-hud')
        commit(repo, {'Docs/Start.md': f'The art went to {ACCOUNT}_old first.\n'}, 'Make the start')
        base.git(repo, 'switch', '-q', 'main')
        r = run(self.inp, '--no-repo-dataset')
        self.assertEqual(r.returncode, 2)
        hits = base.read(os.path.join(repo, '.dataset', f'{SLUG}.refused-hits.tsv'))
        self.assertIn(f'History/{SLUG}.bundle\thistory\tDocs/Start.md', hits)

    def test_the_account_name_glued_into_a_word_refuses(self):
        # OwnerNameDesktop: a lower -> upper boundary is a word's edge, so the name is found where the scrub leaves it
        commit(self.inp['repo'], {'Docs/Owner.md': f'The shortcut was named Owner{ACCOUNT.capitalize()}Desktop.\n'}, 'Add the owner note')
        record(self.inp)
        r = run(self.inp, '--no-repo-dataset')
        self.assertEqual(r.returncode, 2)
        self.assertIn('GodotProject/Docs/Owner.md', base.read(os.path.join(self.inp['repo'], '.dataset', f'{SLUG}.refused-hits.tsv')))

    def test_excluded_session(self):
        r = run(self.inp, '--exclude-sessions', S2, '--no-repo-dataset')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with zipfile.ZipFile(os.path.join(self.inp['repo'], 'Dataset.pending.zip')) as z:
            msgs = [json.loads(l) for l in io.TextIOWrapper(z.open(f'{SLUG}/History/sessions/messages.jsonl'), encoding='utf-8')]
        self.assertEqual({m['session_id'] for m in msgs}, {'session_01'})
        self.assertFalse(os.path.isfile(os.path.join(self.inp['repo'], 'Dataset', 'manifest.json')))


if __name__ == '__main__':
    unittest.main()
