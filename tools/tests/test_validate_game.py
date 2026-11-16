"""tools/validate-game.py on throwaway Godot game repos: a valid one (with five long-thread tasks on its orphan tasks
branch and a full Dataset.zip) and one broken variant per rule. Fixtures are made with plain git, no Godot and no PowerShell.

    python -m unittest discover -s tools/tests -p "test_validate_game.py" -v
"""
import hashlib, importlib.util, io, json, os, re, shutil, stat, subprocess, sys, tempfile, unittest, unittest.mock, warnings
import zipfile

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(TOOLS)
TEMPLATE = os.path.join(REPO, 'templates', 'godot-game')
MOBILE_TEMPLATE = os.path.join(REPO, 'templates', 'godot-game-mobile')


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(TOOLS, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vg = load('validate_game', 'validate-game.py')
SLUG = 'kiln-run'
HAS_LFS = subprocess.run(['git', 'lfs', 'version'], capture_output=True).returncode == 0
ENV = dict(os.environ, GIT_AUTHOR_NAME='dev_1', GIT_AUTHOR_EMAIL='dev_1@example.com', GIT_COMMITTER_NAME='dev_1',
           GIT_COMMITTER_EMAIL='dev_1@example.com', GIT_CONFIG_NOSYSTEM='1')
SIDECARS = vg.SPEC['repo']['sidecars']


def git(repo, *args, input=None):
    r = subprocess.run(['git', '-C', repo, *args], capture_output=True, env=ENV, input=input)
    if r.returncode != 0:
        raise RuntimeError(f'git {" ".join(args)}: {r.stderr.decode(errors="replace")}')
    return r.stdout.decode('utf-8', 'replace').strip()


def read(path, mode='r'):
    with open(path, mode, **({} if 'b' in mode else {'encoding': 'utf-8'})) as f:
        return f.read()


def write(repo, rel, data):
    p = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:
        f.write(data if isinstance(data, bytes) else data.encode('utf-8'))


def uid(rel):
    return 'uid://' + hashlib.md5(rel.encode()).hexdigest()[:13]


def asset(repo, rel, data):
    """rel, and the sidecar the engine keeps beside it: an imported file's .import, a script's .uid."""
    write(repo, rel, data)
    ext = rel.rsplit('.', 1)[-1].lower()
    if ext in SIDECARS['imported_extensions']:
        write(repo, rel + '.import', f'[remap]\n\nimporter="texture"\nuid="{uid(rel)}"\n')
    elif ext in SIDECARS['uid_extensions']:
        write(repo, rel + '.uid', uid(rel) + '\n')


def code(cls, n):
    """A GDScript file of about n lines."""
    lines = [f'class_name {cls}', 'extends Node', '']
    lines += [f'var field{i}: float = {i}.0' for i in range(n - 3)]
    return '\n'.join(lines) + '\n'


SCENE = '[gd_scene format=3]\n\n[node name="{}" type="Node3D"]\n'


def commit(repo, msg):
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', msg)
    return git(repo, 'rev-parse', 'HEAD')


def set_tasks(repo, tasks, extra=None):
    """The orphan tasks branch with Tasks/<name>.json per task (plumbing: the work tree stays on main)."""
    entries = []
    for name, t in tasks.items():
        data = t if isinstance(t, str) else json.dumps(t, indent=2)   # a string as written: a file that is no JSON
        blob = git(repo, 'hash-object', '-w', '--stdin', input=data.encode())
        entries.append(f'100644 blob {blob}\t{name}.json')
    sub = git(repo, 'mktree', input=''.join(e + '\n' for e in entries).encode())
    root_entries = [f'040000 tree {sub}\tTasks']
    readme = git(repo, 'hash-object', '-w', '--stdin', input=b'# Tasks\n')
    root_entries.append(f'100644 blob {readme}\tREADME.md')
    root = git(repo, 'mktree', input=('\n'.join(root_entries) + '\n').encode())
    c = git(repo, 'commit-tree', root, *(extra or []), '-m', 'Tasks')
    git(repo, 'update-ref', 'refs/heads/tasks', c)
    return c


def workflow_row(n, op='project.create', **extra):
    row = {'schema': 'godot-workflow/v0', 'id': f'kr-{n:05d}', 'seq': n, 'time': f'2026-11-0{1 + n % 8}T10:00:00.000+01:00',
           'actor': 'agent', 'op': op, 'target': 'project.godot',
           'params': {'engine': 'godot 4.7.2'}, 'reason': 'Create the project', 'reason_source': 'agent_note',
           'source': {'script': 'new-game.ps1', 'sha256': 'a' * 64, 'commit': None}, 'status': 'observed'}
    row.update(extra)
    return json.dumps(row)


def template(rel, folder=TEMPLATE):
    """A template file as new-game.ps1 fills it in for this game."""
    text = read(os.path.join(folder, rel))
    for mark, value in (('__PROJECT__', 'KilnRun'), ('__TITLE__', 'Kiln Run'), ('__SLUG__', SLUG),
                        ('__GODOT_FEATURE__', vg.ENGINE), ('__ANDROID_NAME__', 'kilnrun')):
        text = text.replace(mark, value)
    return text


def make_game(repo):
    """A Godot 4.7 game with a long thread (4 commits, 6 game files, 124 code lines, 3 systems). Returns
    (start, reference) of that thread."""
    os.makedirs(repo)
    git(repo, 'init', '-q', '-b', 'main')
    hooks = os.path.join(os.path.dirname(repo), 'nohooks')
    os.makedirs(hooks, exist_ok=True)
    for k, v in (('core.hooksPath', hooks), ('core.autocrlf', 'false'), ('commit.gpgsign', 'false'),
                 ('user.name', 'dev_1'), ('user.email', 'dev_1@example.com')):
        git(repo, 'config', k, v)
    git(repo, 'lfs', 'install', '--local', '--skip-repo')   # its filters, none of its hooks (0.4 s a commit)
    for name in ('.gitignore', '.gitattributes'):
        shutil.copy(os.path.join(TEMPLATE, name), os.path.join(repo, name))
    for rel in ('project.godot', 'export_presets.cfg', 'Scripts/godot.ps1', 'Docs/ThirdPartyNotices.md',
                'steps/README.md'):
        write(repo, rel, template(rel))
    for folder in ('Docs', 'Scripts', 'Dataset'):
        write(repo, f'{folder}/.gdignore', '')
    asset(repo, 'scenes/Main.tscn', SCENE.format('Main'))
    asset(repo, 'game/kiln.gd', code('Kiln', 30))
    asset(repo, 'assets/third_party/kenney/crate.png', b'\x89PNG\r\n\x1a\n' + b'\0' * 64)
    write(repo, 'assets/.drafts/ignored.gd', 'extends Node\n')            # the engine skips .name folders: no .uid
    write(repo, 'Docs/screenshots/hero.jpg', b'\xff\xd8\xff' + b'\1' * 64)   # under a .gdignore: no .import
    write(repo, 'README.md', '# Kiln Run\n\n![Kiln Run](Docs/screenshots/hero.jpg)\n\nA game.\n')
    write(repo, 'assets.manifest.json', json.dumps({'schema': 'assets-manifest/v1', 'project': 'KilnRun', 'assets': [
        {'name': 'Crates', 'source': 'Kenney', 'url': 'https://kenney.nl/assets', 'licence': 'CC0 1.0',
         'files': ['assets/third_party/kenney/']}]}, indent=2))
    write(repo, 'workflow.jsonl', workflow_row(1) + '\n' + workflow_row(
        2, op='user.direction', actor='user', target='design', params={'direction': 'Keep the hero on the ground.',
                                                                    'via': 'direct'},
        reason_source='user_direction') + '\n')
    start = commit(repo, 'Create the project')
    asset(repo, 'game/hero.gd', code('Hero', 40))
    start_c1 = commit(repo, 'Add the hero controller')
    asset(repo, 'game/hud.gd', code('Hud', 40))
    commit(repo, 'Add the score HUD')
    asset(repo, 'game/enemy.gd', code('Enemy', 40))
    asset(repo, 'scenes/Hero.tscn', SCENE.format('Hero'))
    commit(repo, 'Add enemies and the hero scene')
    with open(os.path.join(repo, 'project.godot'), 'a', encoding='utf-8', newline='\n') as f:
        f.write('\n[global_group]\n\nHazard=""\n')
    asset(repo, 'game/kiln.gd', code('Kiln', 34))
    ref = commit(repo, 'Group the hazards and fix the kiln')
    assert start_c1
    return start, ref


def task(start, ref, **over):
    t = {
        'name': f'{SLUG}-fix-hero-hud', 'title': 'Hero falls and the score freezes',
        'instruction': 'In scenario 2 the hero drops through the floor near the kiln and the score stops counting.',
        'engine': 'godot-4.7',
        'seed': {'game': SLUG, 'commit': start, 'reference': ref, 'kind': 'bug_fix'},
        'play_scene': 'res://scenes/Main.tscn', 'play_args': ['-scenario', '2'], 'player': {'tag': 'Player'},
        'difficulty': 'hard', 'tags': ['long-thread'],
        'limits': {'max_turns': 400, 'max_minutes': 480, 'max_usd': 150, 'tool_timeout_seconds': 1800},
        'milestones': [
            {'name': 'builds', 'checks': [{'name': 'player_builds', 'kind': 'build', 'weight': 0}]},
            {'name': 'boots', 'checks': [{'name': 'boots_clean', 'kind': 'boot', 'seconds': 60, 'weight': 0,
                                          'needs': ['player_builds']}]},
            {'name': 'fixed', 'checks': [
                {'name': 'hero_on_ground', 'kind': 'probe', 'weight': 3, 'needs': ['boots_clean'],
                 'describe': 'The hero stays on the ground near the kiln.', 'play': 'look',
                 'measure': {'probe': 'player', 'field': 'y', 'window': [3, 18], 'agg': 'min'},
                 'expect': {'op': '>=', 'calibrate': 0.5}},
                {'name': 'score_counts', 'kind': 'probe', 'needs': ['boots_clean'],
                 'describe': 'The score readout rises while the hero collects.',
                 'play': {'name': 'collect', 'seconds': 20, 'scene': 'res://scenes/Main.tscn',
                          'args': ['-scenario', '3'],
                          'inputs': [{'t': 1, 'key': '<Keyboard>/w', 'press': True},
                                     {'t': 6, 'key': '<Keyboard>/w', 'press': False},
                                     {'t': 7, 'key': '<Mouse>/delta/x', 'axis': 4.0},
                                     {'t': 8, 'widget': 'RetryButton', 'click': True}]},
                 'measure': {'probe': 'ui', 'field': 'number', 'agg': 'rises',
                             'select': {'kind': 'text', 'rect': [0, 0, 0.3, 0.1]}},
                 'expect': {'op': '>=', 'value': 1}},
                {'name': 'enemies_move', 'kind': 'probe', 'needs': ['boots_clean'],
                 'describe': 'The enemies move again.', 'play': 'drive',           # selected by what they do:
                 'measure': {'probe': 'objects', 'select': {'has': {'visible': True}},  # Enemy is only the reference's
                             'field': 'speed', 'of': 'max'},
                 'expect': {'op': '>', 'calibrate': 0.5}}]},
            {'name': 'still_works', 'checks': [
                {'name': 'hero_moves', 'kind': 'probe', 'weight': 0, 'needs': ['boots_clean'],
                 'describe': 'The hero still moves.', 'play': 'drive',
                 'measure': {'probe': 'player', 'field': 'moved', 'agg': 'max'}, 'expect': {'op': '>', 'value': 2}}]}]}
    t.update(over)
    return t


TASKS = ('fix-hero-hud', 'feat-enemy-glow', 'fix-kiln-tags', 'feat-score-hud', 'fix-hero-prefab')


def game_tasks(start, ref, **over):
    """The five hard tasks a valid game ships ({name: task}; they share the one thread); over changes the first."""
    tasks = {}
    for i, n in enumerate(TASKS):
        kind = 'feature' if n.startswith('feat-') else 'bug_fix'
        t = task(start, ref, name=f'{SLUG}-{n}', seed={'game': SLUG, 'commit': start, 'reference': ref, 'kind': kind})
        tasks[t['name']] = dict(t, **over) if i == 0 else t
    return tasks


def errors(rep, area=None):
    return [m for s, a, m in rep.items if s == 'error' and (area is None or a.startswith(area))]


def onerror(fn, path, _):
    os.chmod(path, stat.S_IWRITE)
    fn(path)


BASE = {}   # the valid game, made once for the module (it takes seconds); every test works on a copy of it


def tearDownModule():
    if BASE:
        shutil.rmtree(BASE['tmp'], onerror=onerror)


@unittest.skipUnless(HAS_LFS, 'git-lfs is not installed')
class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BASE:
            tmp = tempfile.mkdtemp(prefix='ggfv')
            base = os.path.join(tmp, 'base', SLUG)
            start, ref = make_game(base)
            set_tasks(base, game_tasks(start, ref))
            BASE.update(tmp=tmp, base=base, start=start, ref=ref)
        cls.tmp = tempfile.mkdtemp(prefix='ggfv')
        cls.base, cls.start, cls.ref = BASE['base'], BASE['start'], BASE['ref']

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, onerror=onerror)

    def setUp(self):
        self.n = getattr(type(self), '_n', 0) + 1
        type(self)._n = self.n
        self.repo = os.path.join(self.tmp, f'{self._testMethodName[:20]}{self.n}', SLUG)
        shutil.copytree(self.base, self.repo, symlinks=True)

    def check(self):
        rep = vg.Report()
        vg.check_repo(rep, self.repo)
        return rep


class ValidGame(Base):
    def test_valid_repo(self):
        rep = self.check()
        self.assertEqual(errors(rep), [])
        notes = ' '.join(m for s, a, m in rep.items if s == 'note')
        self.assertIn('project.godot: Godot 4.7', notes)
        self.assertIn('5 task(s) on tasks', notes)

    def test_cli_exit_code(self):
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'validate-game.py'), self.repo, '--quiet'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith('VALID'))

    def test_seed_on_start_branch(self):
        # a made start (godot-write-tasks section 2): S = the thread taken out, R = a child with main's tree
        s = git(self.repo, 'commit-tree', f'{self.start}^{{tree}}', '-p', self.ref, '-m', 'start')
        r = git(self.repo, 'commit-tree', f'{self.ref}^{{tree}}', '-p', s, '-m', 'reference')
        name = f'{SLUG}-fix-hero-hud'
        git(self.repo, 'update-ref', f'refs/heads/starts/{name}', r)
        set_tasks(self.repo, dict(game_tasks(self.start, self.ref), **{name: task(s, r)}))
        self.assertEqual(errors(self.check()), [])
        git(self.repo, 'update-ref', '-d', f'refs/heads/starts/{name}')
        self.assertTrue(any('is not a commit of this game' in e for e in errors(self.check())))


class Sidecars(Base):
    def test_missing_sidecar(self):
        os.remove(os.path.join(self.repo, 'game/kiln.gd.uid'))
        os.remove(os.path.join(self.repo, 'assets/third_party/kenney/crate.png.import'))
        commit(self.repo, 'Lose two sidecars')
        errs = errors(self.check(), 'repo: sidecars')
        self.assertTrue(any(e.startswith('game/kiln.gd: no .uid tracked') for e in errs), errs)
        self.assertTrue(any(e.startswith('assets/third_party/kenney/crate.png: no .import tracked') for e in errs), errs)
        self.assertEqual(len(errs), 2, errs)

    def test_orphan_sidecar(self):
        write(self.repo, 'assets/ghost.png.import', '[remap]\n')
        write(self.repo, 'game/gone.gd.uid', 'uid://b0gone\n')
        write(self.repo, 'game/bad.gd', 'extends Node\n')
        write(self.repo, 'game/bad.gd.uid', 'not a uid\n')
        commit(self.repo, 'Orphans')
        errs = errors(self.check(), 'repo: sidecars')
        self.assertTrue(any(e.startswith('assets/ghost.png.import: its file is not tracked') for e in errs), errs)
        self.assertTrue(any(e.startswith('game/gone.gd.uid: its file is not tracked') for e in errs), errs)
        self.assertTrue(any(e.startswith('game/bad.gd.uid: no uid') for e in errs), errs)
        self.assertEqual(len(errs), 3, errs)

    def test_sidecar_problems_unit(self):
        files = ['assets/a/b.png', 'assets/a/b.png.import', 'assets/c.wav', 'game/hero.gd', 'game/hero.gd.uid',
                 'game/hud.gd', 'game/glow.gdshader', 'assets/.hidden/x.png', '.github/workflows/ci.yml',
                 'Docs/.gdignore', 'Docs/screenshots/hero.jpg', 'Docs/old/shot.png.import', 'steps/build_yard.gd',
                 'assets/data/waves.txt', 'assets/sky.dds', 'assets/z.ogg.import', 'project.godot', 'icon.svg',
                 'icon.svg.import', 'assets/Données/Carte été.png', 'assets/Hero.GLB']
        missing, orphan, sidecars = vg.sidecar_problems(files, set(SIDECARS['imported_extensions']),
                                                        set(SIDECARS['uid_extensions']))
        self.assertEqual(missing, [('assets/Données/Carte été.png', '.import'), ('assets/Hero.GLB', '.import'),
                                   ('assets/c.wav', '.import'), ('assets/sky.dds', '.uid'),
                                   ('game/glow.gdshader', '.uid'), ('game/hud.gd', '.uid'),
                                   ('steps/build_yard.gd', '.uid')])
        self.assertEqual(orphan, ['assets/z.ogg.import'])
        self.assertEqual(sorted(sidecars), ['assets/a/b.png.import', 'assets/z.ogg.import', 'game/hero.gd.uid',
                                            'icon.svg.import'])

    def test_the_template_names_every_sidecar_type_as_text_and_every_imported_type_as_binary(self):
        """An .import and a .uid are plain git text in the template, and the format's lists follow the template's
        .gitattributes: the LFS extensions are its LFS patterns, the text extensions its text patterns."""
        attrs = read(os.path.join(TEMPLATE, '.gitattributes'))
        R = vg.SPEC['repo']
        for ext in ('import', 'uid', 'tscn', 'tres', 'gd', 'gdshader', 'godot', 'cfg'):
            self.assertIn(ext, R['text_extensions'])
            self.assertRegex(attrs, rf'(?m)^\*\.{ext} text eol=lf$')
        lfs = [re.sub(r'\[(.)(.)\]', lambda g: g.group(1).lower(), m)
               for m in re.findall(r'(?m)^\*\.(\S+) filter=lfs diff=lfs merge=lfs -text$', attrs)]
        self.assertEqual(sorted(lfs), sorted(R['lfs_required_extensions']))
        self.assertEqual(set(R['text_extensions']) & set(R['lfs_required_extensions']), set())


class RepoRules(Base):
    def test_banned_name(self):
        write(self.repo, 'assets/data/credits.txt', 'Made with Game-Factory tools.\n')
        write(self.repo, 'assets/data/paths.txt', 'Saved to C:/Users/Kilnmaker/AppData.\n')    # the machine's account
        asset(self.repo, 'steps/build_yard.gd', '# ran from C:/Users/Kilnmaker/Work\nextends SceneTree\n')  # a step that ran
        write(self.repo, 'Dataset/README.md', 'Built with Claude.\n')                       # the packager's, skipped
        commit(self.repo, 'Credits')
        with unittest.mock.patch.dict(os.environ, {'USERNAME': 'Kilnmaker'}):
            errs = errors(self.check(), 'repo: banned names')
        self.assertTrue(any(e.startswith('assets/data/credits.txt') for e in errs), errs)
        self.assertIn('assets/data/paths.txt: the account name x1', errs)
        self.assertEqual(len(errs), 2, errs)

    def test_factory_repo_name_banned(self):
        rx = vg.SPEC['repo']['banned_names']['patterns'][1]
        self.assertTrue(re.search(rx, 'cloned godot_game_factory here'))
        self.assertFalse(re.search(rx, f'the repo godot-game-{SLUG}'))   # a game's own repo name is no tool name

    def test_wrong_engine_and_main_scene(self):
        pg = os.path.join(self.repo, 'project.godot')
        text = read(pg)
        self.assertIn(f'PackedStringArray("{vg.ENGINE}"', text)
        write(self.repo, 'project.godot', text.replace(f'PackedStringArray("{vg.ENGINE}"', 'PackedStringArray("4.3"')
              .replace('res://scenes/Main.tscn', 'res://scenes/Gone.tscn'))
        commit(self.repo, 'Downgrade')
        errs = errors(self.check(), 'repo')
        self.assertIn("project.godot: config/features names Godot '4.3', not Godot 4.7", errs)
        self.assertIn('project.godot: run/main_scene res://scenes/Gone.tscn is not committed', errs)
        write(self.repo, 'project.godot', re.sub(r'(?m)^run/main_scene=.*\n|^config/features=.*\n', '', text))
        commit(self.repo, 'No scene, no engine')
        errs = errors(self.check(), 'repo')
        self.assertIn("project.godot: config/features names Godot '(none)', not Godot 4.7", errs)
        self.assertIn('project.godot: no run/main_scene (the scene the game starts in)', errs)
        os.remove(pg)
        commit(self.repo, 'No project')
        self.assertTrue(any(e.startswith(r'missing ^project\.godot$') for e in errors(self.check(), 'repo')))

    def test_the_format_names_the_machines_engine(self):
        """The engine version the format asks for is the one the machine installs (machine/godot.json `feature`)."""
        pinned = os.path.join(REPO, 'machine', 'godot.json')
        if not os.path.isfile(pinned):
            self.skipTest('no machine/godot.json')
        feature = json.loads(read(pinned))['feature']
        self.assertEqual(vg.SPEC['repo']['engine_versions'], [feature])
        self.assertEqual(vg.ENGINE, feature)
        self.assertEqual(vg.SCHEMAS['game-task']['properties']['engine']['const'], f'godot-{feature}')

    def test_gitignore_hides_assets(self):
        with open(os.path.join(self.repo, '.gitignore'), 'a') as f:
            f.write('Build/\nassets/third_party/\n*.import\n')
        commit(self.repo, 'Ignore too much')
        errs = errors(self.check(), 'repo: .gitignore')
        self.assertTrue(any(e.startswith('game/_probe_/Build/probe.gd would be git-ignored') for e in errs), errs)
        self.assertTrue(any(e.startswith('assets/third_party/_probe_/Probe.glb') for e in errs), errs)
        self.assertTrue(any(e.startswith('assets/_probe_/Probe.png.import') for e in errs), errs)

    def test_generated_folder_tracked_and_not_ignored(self):
        write(self.repo, '.gitignore', '/Dataset.zip\n/Dataset.pending.zip\n')
        write(self.repo, '.godot/global_script_class_cache.cfg', 'list=[]\n')
        write(self.repo, 'android/build/build.gradle', '// template\n')
        write(self.repo, 'release.keystore', 'secret\n')
        commit(self.repo, 'Oops')
        errs = errors(self.check(), 'repo')
        self.assertTrue(any('.godot/global_script_class_cache.cfg' in e for e in errs), errs)
        self.assertTrue(any(e.startswith('.godot/ is not ignored') for e in errs), errs)
        for what in ('(e.g. android/build/build.gradle): build output', '(e.g. release.keystore): a signing keystore',
                     'missing /.dataset/'):
            self.assertTrue(any(what in e for e in errs), (what, errs))

    def test_lfs(self):
        attrs = os.path.join(self.repo, '.gitattributes')
        text = read(attrs).replace('*.[pP][nN][gG] filter=lfs diff=lfs merge=lfs -text', '')
        write(self.repo, '.gitattributes', text + '*.tscn filter=lfs diff=lfs merge=lfs -text\n')
        asset(self.repo, 'assets/art/plain.png', b'\x89PNG\r\n\x1a\n' + b'\2' * 64)
        asset(self.repo, 'scenes/Crate.tscn', SCENE.format('Crate'))
        write(self.repo, 'assets/data/packed.tres', b'\0\1binary, under a text name')
        commit(self.repo, 'LFS mistakes')   # the copy's files are all re-added: the base's crate.png and scenes too
        self.assertIn('scenes/Main.tscn', git(self.repo, 'lfs', 'ls-files', '--name-only'))
        errs = errors(self.check(), 'repo: LFS')
        self.assertEqual(sorted(errs), sorted(
            [f'binary tracked in plain git: {f}' for f in ('assets/third_party/kenney/crate.png', 'assets/art/plain.png')] +
            [f"Godot text or GDScript in LFS: {f} (it loses its diffs and merges; .gitattributes must keep it plain git "
             "text, as the template's does)" for f in ('scenes/Crate.tscn', 'scenes/Hero.tscn', 'scenes/Main.tscn')]))
        self.assertIn(('warning', 'repo: LFS', 'binary content in plain git: assets/data/packed.tres (give its type an '
                       'LFS pattern in .gitattributes)'), self.check().items)
        real = subprocess.run

        def no_lfs(args, **kw):   # a machine without Git LFS: git says lfs is no git command
            if 'lfs' in args:
                return subprocess.CompletedProcess(args, 1, '', "git: 'lfs' is not a git command.")
            return real(args, **kw)
        with unittest.mock.patch.object(vg.subprocess, 'run', no_lfs):
            errs = errors(self.check(), 'repo: LFS')
        self.assertEqual(len(errs), 1, errs)
        self.assertTrue(errs[0].startswith('git lfs ls-files failed, so LFS is not checked'), errs)

    def test_assets_manifest(self):
        data = json.loads(read(os.path.join(self.repo, 'assets.manifest.json')))
        data['assets'].append({'name': 'Gone', 'source': 'x', 'url': 'https://x', 'licence': 'CC0',
                               'files': ['Content/Gone/', 'assets/Gone.glb']})
        crate = 'assets/third_party/kenney/crate.png'
        data['assets'] += [{'name': 'Ours', 'source': 'the studio', 'origin': 'studio', 'licence': 'own',
                            'files': [crate]},     # the schema's if: studio needs a description
                           {'name': 'Theirs', 'source': 'x', 'licence': 'CC0', 'files': [crate]}]   # else: an https url
        write(self.repo, 'assets.manifest.json', json.dumps(data))
        commit(self.repo, 'Manifest')
        errs = errors(self.check(), 'repo: assets.manifest.json')
        self.assertIn('asset path outside assets/ or addons/: Gone: Content/Gone/', errs)
        self.assertIn('listed asset file not present: Gone: assets/Gone.glb', errs)
        self.assertIn('$.assets[2] (Ours): origin studio needs a "description"', errs)
        self.assertTrue(any(e.startswith('$.assets[3] (Theirs): needs an https "url"') for e in errs), errs)

    def test_workflow_rows(self):
        with open(os.path.join(self.repo, 'workflow.jsonl'), 'a') as f:
            f.write(workflow_row(2) + '\n' + workflow_row(3, schema='other-workflow/v0') + '\n')
        commit(self.repo, 'Bad rows')
        errs = errors(self.check(), 'repo: workflow.jsonl')
        self.assertTrue(any('duplicate id kr-00002' in e for e in errs), errs)
        self.assertTrue(any('other-workflow/v0' in e for e in errs), errs)

    def test_readme(self):
        write(self.repo, 'README.md', '# Kiln Run\n\n![hero](Docs/screenshots/hero.jpg "The kiln")\n'
              '<img src="./Docs/screenshots/gone.jpg">\n![web](https://example.com/x.png)\n<!-- ![old](old.png) -->\n')
        commit(self.repo, 'Readme')
        rep = self.check()
        self.assertEqual(errors(rep, 'repo: README'), ['links Docs/screenshots/gone.jpg, which is not committed'])
        self.assertIn(('warning', 'repo: README', '2 images; the rule is a hero + gallery of 5-7 gameplay stills'),
                      rep.items)
        write(self.repo, 'README.md', '# Kiln Run\n\nNo stills yet.\n')
        commit(self.repo, 'Readme without stills')
        self.assertEqual(errors(self.check(), 'repo: README'), ['shows no gameplay image'])
        for f in ('workflow.jsonl', 'assets.manifest.json'):   # tracked, gone from the checkout: an error, no traceback
            os.remove(os.path.join(self.repo, f))
        self.assertEqual(errors(self.check(), 'repo')[0], '2 tracked file(s) not in the working tree (e.g. '
                                                          'assets.manifest.json): check out the release commit as it is')

    def test_task_files(self):
        set_tasks(self.repo, {f'{SLUG}-a': 'not json', f'{SLUG}-b': [1],
                              f'{SLUG}-c': task(self.start, self.ref, name='other')})
        errs = errors(self.check(), 'repo: Tasks')
        for what in (f'tasks:Tasks/{SLUG}-a.json: not JSON', f'tasks:Tasks/{SLUG}-b.json: not a task object',
                     f"tasks:Tasks/{SLUG}-c.json: name 'other' differs from the file name"):
            self.assertTrue(any(e.startswith(what) for e in errs), (what, errs))
        set_tasks(self.repo, {})
        self.assertTrue(any(e.startswith('no task files in Tasks/ on tasks') for e in errors(self.check(), 'repo: Tasks')))

    def test_tasks_on_main(self):
        write(self.repo, f'Tasks/{SLUG}-x.json', '{}')
        commit(self.repo, 'Tasks on main')
        errs = errors(self.check(), 'repo: Tasks')
        self.assertTrue(any(e.startswith('main tracks 1 path(s) under Tasks/') for e in errs), errs)

    def test_tasks_branch_not_orphan(self):
        set_tasks(self.repo, game_tasks(self.start, self.ref), extra=['-p', self.ref])
        self.assertTrue(any('shares history with main' in e for e in errors(self.check(), 'repo: Tasks')))

    def test_no_tasks_branch(self):
        git(self.repo, 'update-ref', '-d', 'refs/heads/tasks')
        self.assertTrue(any(e.startswith('no tasks branch') for e in errors(self.check(), 'repo: Tasks')))


class TaskRules(Base):
    def check(self):   # these tests change the tasks branch alone: its rules, without the rest of the repo's
        rep = vg.Report()
        vg.check_repo_tasks(rep, self.repo)
        return rep

    def tasks(self, **over):
        set_tasks(self.repo, game_tasks(self.start, self.ref, **over))
        return errors(self.check(), 'repo: Tasks')

    def probe(self, i, **measure):
        t = task(self.start, self.ref)
        t['milestones'][2]['checks'][i]['measure'] = measure
        return t['milestones']

    def test_easy(self):
        errs = self.tasks(difficulty='easy')
        self.assertTrue(any("difficulty 'easy'" in e for e in errs), errs)

    def test_fewer_than_five_tasks(self):
        tasks = game_tasks(self.start, self.ref)
        del tasks[f'{SLUG}-{TASKS[-1]}']
        set_tasks(self.repo, tasks)
        self.assertEqual(errors(self.check(), 'repo: Tasks'),
                         ['tasks: 4 task(s): a game ships at least 5 (godot-write-tasks section 1)'])

    def test_at_least_four_hard(self):
        self.assertEqual(self.tasks(difficulty='medium'), [])   # four hard and one medium: the game stands
        tasks = game_tasks(self.start, self.ref, difficulty='medium')
        del tasks[f'{SLUG}-{TASKS[1]}']['difficulty']           # no difficulty: medium, the schema's default
        set_tasks(self.repo, tasks)
        self.assertEqual(errors(self.check(), 'repo: Tasks'),
                         [f'tasks: 3 hard task(s): a game needs at least 4 hard tasks (medium: {SLUG}-{TASKS[1]}, '
                          f'{SLUG}-{TASKS[0]}); the others may be medium (godot-write-tasks section 1)'])
        tasks[f'{SLUG}-{TASKS[0]}']['difficulty'] = 'hard'
        set_tasks(self.repo, tasks)
        self.assertEqual(errors(self.check(), 'repo: Tasks'), [])   # four hard, and the one that names none is medium
        for i in range(6):                                      # ten tasks, four hard and six medium: the game stands
            t = dict(tasks[f'{SLUG}-{TASKS[0]}'], name=f'{SLUG}-fix-more-{i}', difficulty='medium')
            tasks[t['name']] = t
        set_tasks(self.repo, tasks)
        self.assertEqual(errors(self.check(), 'repo: Tasks'), [])

    def test_reference_only_name(self):
        ms = self.probe(2, probe='objects', select={'component': 'Enemy', 'has': {'visible': True}}, field='speed', of='max')
        self.assertEqual(self.tasks(milestones=ms),
                         [f'tasks:Tasks/{SLUG}-{TASKS[0]}.json: check enemies_move names Enemy, which only the reference '
                          'has: another fair build names it otherwise; select by what it does or where it is '
                          '(godot-write-tasks section 5)'])
        ms[2]['checks'][2]['measure']['select']['component'] = 'Kiln'   # the start has it: any build can match it
        self.assertEqual(self.tasks(milestones=ms), [])
        for name in ('enemy', 'Hazard'):   # a script by its file name, a group project.godot lists: the reference's
            ms[2]['checks'][2]['measure']['select'] = {'component' if name == 'enemy' else 'tag': name}
            self.assertEqual(len(self.tasks(milestones=ms)), 1, name)
        ms[2]['checks'][2]['required'] = False                          # an optional probe gates nothing
        errs = self.tasks(milestones=ms)
        self.assertFalse([e for e in errs if 'only the reference' in e], errs)
        ms = task(self.start, self.ref)['milestones']                   # a scene only the reference has
        ms[2]['checks'][1]['play']['scene'] = 'res://scenes/Hero.tscn'
        self.assertEqual(len([e for e in self.tasks(milestones=ms) if 'names res://scenes/Hero.tscn, which only' in e]), 1)
        ms = task(self.start, self.ref)['milestones']                   # a contact stage's select
        ms[2]['checks'][1]['play']['inputs'].append({'t': 3, 'pin': {'component': 'Enemy'}, 'hold': 1})
        self.assertEqual(len([e for e in self.tasks(milestones=ms) if 'names Enemy, which only the reference' in e]), 1)

    def test_never_literal(self):
        ms = self.probe(2, probe='objects', select={'component': 'Kiln'}, field='spin', of='max')
        ms[2]['checks'][2]['expect'] = {'op': '>', 'value': 3}
        errs = self.tasks(milestones=ms)
        self.assertTrue(any("objects measure's spin depends on what a build chose" in e for e in errs), errs)
        for probe, field in (('audio', 'level'), ('components', 'intensity'), ('components', 'extent_y')):
            m = {'probe': probe, 'field': field}
            if probe == 'components':
                m['select'] = {'component': 'Light3D'}
            c = {'name': 'x', 'kind': 'probe', 'describe': 'x', 'play': 'look', 'measure': m,
                 'expect': {'op': '>', 'value': 0.1}}
            self.assertEqual(list(vg.check_schema(c, vg.SCHEMAS['game-task']['$defs']['Probe'],
                                                  vg.SCHEMAS['game-task'])), [], field)
            self.assertTrue(any('never a literal' in e for e in vg.probe_errors(c, {}, 'r', {})), field)

    def test_every_never_literal_field_is_a_field_of_its_kind(self):
        """A field named in NEVER_LITERAL is one the schema has for that kind (a rule for a field that is gone would
        never be checked)."""
        S = vg.SCHEMAS['game-task']
        kinds = S['$defs']['Probe']['properties']['measure']['discriminator']['mapping']
        for probe, fields in vg.NEVER_LITERAL.items():
            schema = S['$defs'][kinds[probe].split('/')[-1]]['properties']['field']
            for f in fields:
                self.assertEqual(list(vg.check_schema(f, schema, S)), [], (probe, f))

    def test_refused_play_args(self):
        ms = task(self.start, self.ref)['milestones']
        ms[2]['checks'][1]['play']['args'] = ['--fullscreen', '100', '--taskProbe=x', '-Scenario', 'quit-field']
        errs = self.tasks(play_args=['--headless', '-scenario', '2'], milestones=ms)
        self.assertTrue(any("play_args can't set -headless" in e for e in errs), errs)
        self.assertTrue(any("a task play can't set -fullscreen" in e for e in errs), errs)
        self.assertTrue(any("a task play can't set -taskProbe" in e for e in errs), errs)
        self.assertFalse(any('Scenario' in e or 'quit-field' in e for e in errs), errs)

    def test_denied_play_args_unit(self):
        self.assertEqual(list(vg.denied_play_args(
            ['--headless', '--path', 'x', '--log-file', 'x', '--fixed-fps', '30', '--disable-vsync', '--audio-driver',
             'Dummy', '--quit', '--quit-after', '5', '--script', 'x.gd', '--import', '--editor', '--main-pack', 'x.pck',
             '--display-driver', 'headless', '--position', '0,0', '--screen', '1', '--Fullscreen', '-maximized',
             '--windowed', '--single-window', '-shots', '4', '-shotDir', 'x', '-taskProbeSeconds=9', '-ok', 'headless',
             '-autoplay', '-scenario', '2', '-size', '960x540', '--resolution', '1280x720', '--rendering-method',
             'forward_plus', '--Rendering-Driver', 'vulkan', '--write-movie', 'x.avi', 'size', 'rendering-method'])),
            ['headless', 'path', 'log-file', 'fixed-fps', 'disable-vsync', 'audio-driver', 'quit', 'quit-after',
             'script', 'import', 'editor', 'main-pack', 'display-driver', 'position', 'screen', 'Fullscreen',
             'maximized', 'windowed', 'single-window', 'shots', 'shotDir', 'taskProbeSeconds', 'size', 'resolution',
             'rendering-method', 'Rendering-Driver', 'write-movie'])

    def test_bad_schema_field(self):
        ms = self.probe(2, probe='objects', select={'class': 'Enemy'}, field='bb:Speed')
        errs = self.tasks(milestones=ms, play_map='/Game/Maps/L_X')
        self.assertTrue(any('unexpected key "play_map"' in e for e in errs), errs)
        self.assertTrue(any('measure.select: unexpected key "class"' in e for e in errs), errs)
        self.assertTrue(any("measure.field: 'bb:Speed' does not match" in e for e in errs), errs)

    def test_seed_not_the_factorys_engine(self):
        old_project = read(os.path.join(self.repo, 'project.godot')).replace(f'"{vg.ENGINE}"', '"4.3"')
        pv = git(self.repo, 'hash-object', '-w', '--stdin', input=old_project.encode())
        git(self.repo, 'read-tree', self.start)
        git(self.repo, 'update-index', '--add', '--cacheinfo', f'100644,{pv},project.godot')
        tree = git(self.repo, 'write-tree')
        git(self.repo, 'read-tree', 'HEAD')
        old = git(self.repo, 'commit-tree', tree, '-p', self.ref, '-m', 'old engine')
        r = git(self.repo, 'commit-tree', f'{self.ref}^{{tree}}', '-p', old, '-m', 'ref')
        name = f'{SLUG}-fix-hero-hud'
        git(self.repo, 'update-ref', f'refs/heads/starts/{name}', r)
        set_tasks(self.repo, dict(game_tasks(self.start, self.ref), **{name: task(old, r)}))
        errs = errors(self.check(), 'repo: Tasks')
        self.assertTrue(any(f'seed.commit {old[:12]} is a Godot 4.3 project' in e for e in errs), errs)
        self.assertFalse(any('seed.reference' in e and 'project' in e for e in errs), errs)

    def test_short_thread(self):
        errs = self.tasks(seed={'game': SLUG, 'commit': git(self.repo, 'rev-parse', f'{self.ref}~1'),
                                'reference': self.ref, 'kind': 'bug_fix'})
        for floor in ('game file(s) against the start, fewer than 5', 'code line(s) against the start, fewer than 100',
                      'commit(s) change the game from seed.commit to seed.reference, fewer than 4'):
            self.assertTrue(any(floor in e for e in errs), (floor, errs))
        if not os.path.isfile(os.path.join(TOOLS, 'thread-stats.py')):
            self.skipTest('no thread-stats.py')
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'thread-stats.py'), self.repo, self.ref, '--span',
                            f'{self.start}..{self.ref}'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)   # counted as the validator counts: the whole thread meets the floors
        self.assertIn('span: 4 game commit(s), 6 game file(s), 124 code line(s), 3 system(s) (code, config, scene)',
                      r.stdout)
        self.assertIn('below the floors on its own: 1 game commits (floor 4); 2 game files (floor 5)', r.stdout)

    def test_noop_and_outcomes(self):
        ms = task(self.start, self.ref)['milestones']
        ms[0]['checks'][0]['weight'] = 1
        del ms[2]['checks'][2]
        errs = self.tasks(milestones=ms, tags=[], seed={'game': 'other', 'commit': self.start, 'kind': 'feature'})
        for what in ('a no-op passes it', 'no long-thread tag', 'no seed.reference', 'fewer than 3',
                     "seed.game 'other' is not this game"):
            self.assertTrue(any(what in e for e in errs), (what, errs))

    def test_a_weight_0_guard_is_no_outcome(self):
        ms = task(self.start, self.ref)['milestones']
        self.assertEqual(self.tasks(milestones=ms), [])
        ms[2]['checks'][2]['weight'] = 0   # a guard: it gates and pays nothing
        self.assertEqual(self.tasks(milestones=ms),
                         [f'tasks:Tasks/{SLUG}-{TASKS[0]}.json: 2 required outcome probe(s) outside still_works, fewer '
                          'than 3 (a required probe of weight 0 is a guard, not an outcome) (godot-write-tasks section 1: '
                          'only long threads of multiple edits)'])
        guard = dict(ms[2]['checks'][2], name='hud_kept_guard')
        ms[2]['checks'][2]['weight'] = 1
        ms[2]['checks'].append(guard)      # a guard beside three outcomes
        self.assertEqual(self.tasks(milestones=ms), [])

    def test_probe_rules(self):
        t = task(self.start, self.ref)
        checks = t['milestones'][2]['checks']
        checks[0]['measure'] = {'probe': 'player', 'field': 'dist', 'agg': 'min'}
        checks[2]['measure'] = {'probe': 'components', 'select': {'near': {'point': {'player': True}, 'radius': 5,
                                                                          'y_min': 2, 'y_max': 1}}, 'field': 'count'}
        errs = vg.task_semantic_errors(t)
        for what in ('dist is the distance to its `to` point', 'names its component, or `effect`', 'y_min < y_max'):
            self.assertTrue(any(what in e for e in errs), (what, errs))

    def test_no_games_tasks_choose_a_renderer_or_a_size(self):
        ms = task(self.start, self.ref)['milestones']
        ms[2]['checks'][1]['play']['args'] = ['-scenario', '3', '--rendering-method', 'forward_plus']
        errs = self.tasks(play_args=['-size', '1280x720'], milestones=ms)
        self.assertTrue(any("play_args can't set -size" in e for e in errs), errs)
        self.assertTrue(any("a task play can't set -rendering-method" in e for e in errs), errs)


class Units(unittest.TestCase):
    """The validator's rules on their own, without a repo."""

    def test_thread_definitions(self):
        """The seven systems a game file falls into; a step (the creation's record), an .import, a .uid, the AutoPlay
        drop-in or the task probe is no game file, though a step's lines are code lines."""
        for path, system in (('game/hero.gd', 'code'), ('game/ui/Hud.GD', 'code'), ('project.godot', 'config'),
                             ('addons/dialogue/plugin.cfg', 'addon'), ('addons/dialogue/dialogue.gd', 'addon'),
                             ('scenes/Yard.tscn', 'scene'), ('scenes/baked/Yard.scn', 'scene'),
                             ('assets/shaders/glow.gdshader', 'material'), ('assets/shaders/noise.gdshaderinc', 'material'),
                             ('assets/art/Crate.PNG', 'material'), ('assets/icon.svg', 'material'),
                             ('assets/materials/bulb.tres', 'data'), ('assets/data/waves.csv', 'data'),
                             ('game/levels.json', 'data'), ('assets/audio/hit.wav', 'asset'),
                             ('assets/models/crate.glb', 'asset'), ('assets/fonts/ui.ttf', 'asset')):
            self.assertEqual(vg.thread_system(path), system, path)
            self.assertIsNotNone(vg.GAME_FILE.search(path), path)
        for path in ('steps/build_yard.gd', 'game/hero.gd.uid', 'assets/art/crate.png.import', 'workflow.jsonl',
                     'Docs/Design.md', 'Scripts/godot.ps1', 'addons/autoplay/autoplay.gd',
                     'addons/task_probe/task_probe.gd', 'export_presets.cfg', 'Platform.json', 'gameplay/notes.md'):
            self.assertIsNone(vg.GAME_FILE.search(path), path)
        numstat = ('40\t0\tsteps/build_yard.gd\n1\t0\tsteps/build_yard.gd.uid\n'
                   '9\t3\tscenes/Yard.tscn\n-\t-\tassets/art/crate.png\n30\t0\tassets/third_party/pack/pack.gd\n'
                   '25\t5\tgame/hero.gd\n')
        self.assertEqual(vg.thread_size(numstat), (40 + 25 + 5, 3))   # code, scene, material

    def test_task_bar(self):
        """A game's bar: at least 5 tasks, at least 4 of them hard; the others may be medium (what a task that names
        none is)."""
        hard = {f't{i}': 'hard' for i in range(5)}
        self.assertEqual(vg.task_bar_errors(hard), [])
        self.assertEqual(vg.task_bar_errors(dict(hard, t0='medium')), [])   # 4 hard + 1 medium
        self.assertEqual(vg.task_bar_errors(dict(hard, t0=None)), [])
        self.assertEqual(vg.task_bar_errors(dict({f'm{i}': 'medium' for i in range(6)}, t0='hard', t1='hard', t2='hard',
                                                 t3='hard')), [])           # 10 tasks: 4 hard + 6 medium
        self.assertEqual(vg.task_bar_errors(dict(hard, t4='medium', t1=None)),   # 3 hard + 2 medium
                         ['3 hard task(s): a game needs at least 4 hard tasks (medium: t1, t4); the others may be medium'])
        self.assertEqual(vg.task_bar_errors({f't{i}': 'hard' for i in range(4)}), ['4 task(s): a game ships at least 5'])
        self.assertEqual(vg.task_bar_errors({'t0': 'hard', 't1': 'hard'}),
                         ['2 task(s): a game ships at least 5',
                          '2 hard task(s): a game needs at least 4 hard tasks; the others may be medium'])
        self.assertEqual(vg.task_bar_errors(dict(hard, t0='easy')), [])   # an easy task is thread_errors' finding
        self.assertEqual(vg.task_bar_errors(dict(hard, t0='trivial')), ['t0: difficulty \'trivial\': a task is "hard"'])
        self.assertEqual(vg.thread_errors({'difficulty': 'easy'}, 3)[0],
                         'difficulty \'easy\': a task is "hard" or "medium" (a game needs at least 4 "hard")')
        self.assertTrue(any("difficulty 'easy'" in e for e in vg.thread_errors({'difficulty': 'easy'}, 3)))

    def test_game_paths(self):
        """The git pathspecs that count a thread's game files and commits (GAME_PATHS) name exactly the files GAME_FILE
        matches, which the systems and thread-stats.py count: no step, no .import, no .uid, any name."""
        tmp = tempfile.mkdtemp(prefix='ggfp')
        self.addCleanup(shutil.rmtree, tmp, onerror=onerror)
        git(tmp, 'init', '-q')
        paths = ['game/hero.gd', 'game/hero.gd.uid', 'steps/build_yard.gd', 'steps/build_yard.gd.uid',
                 'scenes/Yard.tscn', 'scenes_old/Keep.tscn', 'assets/Données/Carte été.tres',
                 'assets/Store Pack/Sky Box.png', 'assets/Store Pack/Sky Box.png.import', 'addons/dialogue/plugin.cfg',
                 'addons/autoplay/autoplay.gd', 'addons/autoplay_extra/keep.gd', 'addons/task_probe/task_probe.gd',
                 'project.godot', 'project.godot.bak', 'export_presets.cfg', 'Scripts/godot.ps1', 'Docs/Design.md',
                 'workflow.jsonl', 'icon.svg']
        blob = git(tmp, 'hash-object', '-w', '--stdin', input=b'')
        git(tmp, 'update-index', '-z', '--index-info', input=''.join(f'100644 {blob}\t{p}\0' for p in paths).encode())
        listed = git(tmp, '-c', 'core.quotepath=off', 'ls-files', '-z', '--', *vg.GAME_PATHS).split('\0')
        self.assertEqual(sorted(p for p in listed if p), sorted(p for p in paths if vg.GAME_FILE.search(p)))
        self.assertIn('addons/autoplay_extra/keep.gd', listed)

    def test_what_a_run_would_refuse(self):
        """What the probe or the checker refuses at run time (or stops on) is refused when the task is written."""
        def errs(measure, play='look', expect=None):
            c = {'name': 'p', 'kind': 'probe', 'describe': 'x', 'play': play, 'measure': measure,
                 'expect': expect or {'op': '>=', 'calibrate': 0.5}}
            return ' | '.join(vg.task_semantic_errors(task('a' * 40, 'b' * 40, milestones=[{'name': 'm', 'checks': [c]}])))
        self.assertIn('a screen rect is [x0, y0, x1, y1] with x0 < x1 and y0 < y1',
                      errs({'probe': 'screen', 'rect': [0.75, 0.25, 0.25, 0.75], 'field': 'luminance'}))
        dist = {'probe': 'player', 'field': 'dist', 'agg': 'min'}
        self.assertIn("a player measure's dist is the distance to its `to` point, which it lacks", errs(dist))
        self.assertEqual(errs(dict(dist, to={'xyz': [0, 0, 0]})), '')
        self.assertIn('`to_angle` or `to_axis`, not both',
                      errs({'probe': 'camera', 'field': 'yaw', 'to_angle': 90, 'to_axis': 0}, expect={'op': '<=', 'value': 5}))
        look = {'probe': 'player', 'field': 'y', 'agg': 'min'}
        self.assertIn('play fire: res://scenes/../X.tscn has a "." or ".." part',
                      errs(look, {'name': 'fire', 'seconds': 5, 'scene': 'res://scenes/../X.tscn'},
                           {'op': '>=', 'value': 0}))
        self.assertIn('play_scene: res://../X.tscn has a "." or ".." part', ' '.join(vg.task_semantic_errors(
            task('a' * 40, 'b' * 40, play_scene='res://../X.tscn'))))
        self.assertEqual(errs(look, {'name': 'fire', 'seconds': 5, 'scene': 'res://scenes/Hero.v2/Road..tscn'},
                              {'op': '>=', 'value': 0}), '', 'dots inside a name are a name')
        # an empty part: the schema's pattern lets these through, the engine opens no such scene
        for path in ('res://scenes//X.tscn', 'res:///X.tscn'):
            self.assertIn(f'play_scene: {path} has an empty part', ' '.join(vg.task_semantic_errors(
                task('a' * 40, 'b' * 40, play_scene=path))))
            self.assertIn(f'play fire: {path} has an empty part',
                          errs(look, {'name': 'fire', 'seconds': 5, 'inputs': [{'t': 1, 'scene': path}]},
                               {'op': '>=', 'value': 0}))
        height = {'probe': 'player', 'field': 'y', 'window': [0, 1], 'at': [5.0]}
        self.assertIn('`window` or `at`, not both', errs(height, expect={'op': '>=', 'value': 0}))
        self.assertEqual(errs(dict(height, at=None), expect={'op': '>=', 'value': 0}), '')
        literal = {'op': '>=', 'value': 1}
        for measure in ({'probe': 'log', 'pattern': '([unclosed'}, {'probe': 'widgets', 'select': {'text': '[a'}},
                        {'probe': 'objects', 'select': {'name': 'Hud'}, 'field': 'prop:label', 'match': '(', 'of': 'first'}):
            self.assertIn("isn't a regular expression", errs(measure, expect=literal), measure)
        for player in ({'player': True}, {'tag': 'Hero', 'near': {'point': {'player': True}, 'radius': 2}}):
            self.assertIn('player: this select says which object the player is',
                          ' '.join(vg.task_semantic_errors(task('a' * 40, 'b' * 40, player=player))), player)
        self.assertEqual(vg.task_semantic_errors(task('a' * 40, 'b' * 40, player={
            'tag': 'Hero', 'near': {'point': {'camera': True, 'forward': 2}, 'radius': 9}})), [])
        absent = {'name': 'clean', 'kind': 'log_absent', 'pattern': 'Exception('}
        self.assertIn("'Exception(' isn't a regular expression",
                      ' '.join(vg.task_semantic_errors(task('a' * 40, 'b' * 40, milestones=[{'name': 'm', 'checks': [absent]}]))))

    def test_task_rules(self):
        """The rules beyond the schema the other tests leave out: task plays, the ui measure's own rules, a threshold
        from the start, a start that doesn't build, judges, check names and needs, and a task without a required
        probe."""
        def errs(*checks, **over):
            t = task('a' * 40, 'b' * 40, milestones=[{'name': 'm', 'checks': list(checks)}], **over)
            return ' | '.join(vg.task_semantic_errors(t))

        def probe(measure, play='look', expect=None, name='p'):
            return {'name': name, 'kind': 'probe', 'describe': 'x', 'play': play, 'measure': measure,
                    'expect': expect or {'op': '>=', 'value': 1}}
        x, near = {'probe': 'player', 'field': 'x'}, {'point': {'xyz': [0, 0, 0]}, 'radius': 1}
        key, wait = {'t': 5, 'key': '<Keyboard>/w', 'press': True}, {'t': 1, 'wait': 200}
        for check, said in (
                (probe(x, {'name': 'drive', 'seconds': 10}), "check p: a task play can't be named drive"),
                (probe(x, {'name': 'fire', 'seconds': 5, 'inputs': [key]}),
                 'check p: play fire has an input at or after its end (5 s)'),
                (probe(x, {'name': 'fire', 'seconds': 60, 'inputs': [wait, dict(wait, t=2)]}),
                 'check p: play fire waits 400 s in all, more than 300 s'),
                (probe(x, {'name': 'fire', 'seconds': 9, 'inputs': [{'t': 1, 'view': [95, 0]}]}),
                 'check p: play fire has a view [95, 0]'),
                (probe(x, {'name': 'fire', 'seconds': 9, 'inputs': [{'t': 1, 'shot': 'a'}, {'t': 2, 'shot': 'a'}]}),
                 'check p: play fire names a shot twice'),
                (probe({'probe': 'ui', 'field': 'count', 'select': {'rect': [0.5, 0, 0.2, 1]}}),
                 'check p: a ui select rect is [x0, y0, x1, y1] with x0 < x1 and y0 < y1'),
                (probe({'probe': 'ui', 'field': 'count', 'select': {'kind': 'box', 'text': 'x'}}),
                 "check p: a ui select's `text` picks text elements"),
                (probe({'probe': 'ui', 'field': 'text'}), 'check p: a ui measure takes `match` exactly when its field is text'),
                (probe({'probe': 'ui', 'field': 'signature', 'agg': 'max'}),
                 'check p: a ui signature is read with `agg` changes, any, all or count'),
                (probe(x, expect={'op': '==', 'calibrate': 1}), 'check p: == and != take a literal value'),
                (probe(x, expect={'op': '>=', 'start_plus': 1}), 'check p sets its threshold from the start')):
            self.assertIn(said, errs(check, seed=None) if 'from the start' in said else errs(check), said)
        self.assertIn("check p calibrates against a reference the task's seed doesn't name",
                      errs(probe(x, expect={'op': '>=', 'calibrate': 1}), seed={'game': SLUG, 'commit': 'a' * 40,
                                                                               'kind': 'feature'}))
        rubric = [{'key': 'k', 'criterion': 'c'}]
        broken = {'name': 'b', 'kind': 'build', 'fails_at_start': True}
        before = {'name': 'j', 'kind': 'judge', 'question': 'q', 'rubric': rubric, 'before': True}
        said = errs(broken, probe(x, expect={'op': '>=', 'start_plus': 1}), before)
        self.assertIn("check p: its threshold is relative to the start (start_plus), but the start doesn't build "
                      '(b: fails_at_start)', said)
        self.assertIn("check j compares with the start (before: true), but the start doesn't build", said)
        said = errs({'name': 'c', 'kind': 'code_judge', 'question': 'q', 'rubric': rubric}, before,
                    dict(before, name='r', before=False, reference=True), seed=None)
        for what in ('check c: a code judge needs seed.reference', 'check j: a before/after judge needs a seed',
                     'check r: a reference judge needs seed.reference'):
            self.assertIn(what, said)
        menu = {'name': 'menu', 'seconds': 6, 'inputs': [{'t': 1, 'key': '<Keyboard>/u', 'press': True}]}
        shown = dict(before, before=False, plays=[menu])
        self.assertEqual(errs(probe(x, menu), shown, dict(shown, name='k', shots=20)), '')
        self.assertEqual(errs(dict(shown, plays=[dict(menu, name=f'm{i}') for i in range(4)])), '')
        for check, said in (
                (dict(shown, plays=[menu, menu]), 'judge check j names a play twice'),
                (dict(shown, plays=[dict(menu, name='look')]), "check j: a task play can't be named look"),
                (dict(shown, plays=[dict(menu, seconds=5, inputs=[key])]), 'check j: play menu has an input at or after'),
                (dict(shown, plays=[dict(menu, args=['--headless'])]), "check j: a task play can't set -headless"),
                (dict(shown, plays=[dict(menu, scene='res://../A.tscn')]), 'check j: play menu: res://../A.tscn has'),
                (dict(shown, plays=[dict(menu, inputs=[{'t': 1, 'teleport_to': {
                    'tag': 'Ore', 'near': dict(near, y_min=5, y_max=1)}}])]), 'check j: a near band has y_min < y_max'),
                (dict(before, before=False, shots=8), 'judge check j sets shots but names no play of its own'),
                (dict(shown, plays=[menu, dict(menu, name='m2')], shots=11),
                 "judge check j asks 2 plays of 11 screenshots: more than a judge's 20"),
                (dict(shown, plays=[dict(menu, name=f'm{i}') for i in range(4)], shots=6), "more than a judge's 20")):
            self.assertIn(said, errs(check), said)
        self.assertIn('check j: task play menu differs from another play of that name',
                      errs(probe(x, menu), dict(shown, plays=[dict(menu, seconds=9)])))
        self.assertIn('check p: task play menu differs from another play of that name',
                      errs(shown, probe(x, dict(menu, seconds=9))))
        coin = dict(shown, plays=[dict(menu, inputs=[{'t': 1, 'teleport_to': {'name': 'Coin*'}}])])
        t = task('a' * 40, 'b' * 40, milestones=[{'name': 'm', 'checks': [coin]}])
        self.assertIn('play menu: teleport_to {"name": "Coin*"} goes to the nearest', ' | '.join(vg.task_warnings(t)))
        ok = lambda v: list(vg.check_schema(v, vg.SCHEMAS['game-task']['$defs']['Judge'], vg.SCHEMAS['game-task']))  # noqa: E731
        self.assertEqual(ok(dict(shown, shots=20)), [])
        for bad in (dict(shown, shots=1), dict(shown, shots=21), dict(shown, shots=7.5), dict(shown, plays=['look']),
                    dict(shown, plays=[dict(menu, name=f'm{i}') for i in range(5)])):
            self.assertNotEqual(ok(bad), [], bad)
        said = errs(probe(x), probe(x), dict(broken, name='q', needs=['p', 'z']))
        self.assertIn('check p is named twice', said)
        self.assertIn("check q needs ['z'], which come later or do not exist", said)
        t = task('a' * 40, 'b' * 40)
        for c in (c for m in t['milestones'] for c in m['checks'] if c['kind'] == 'probe'):
            c['required'] = False
        rep = vg.Report()
        vg.check_task(rep, 'repo: Tasks', 'x', t, SLUG, None)
        self.assertIn('x: no required probe check: pass/fail must be deterministic (godot-write-tasks section 5)',
                      errors(rep))

    def test_touches(self):
        """A touch ends inside its play, and a finger stays up TOUCH_GAP before it goes down again; touches of
        different fingers may overlap."""
        def errs(*inputs, seconds=10):
            c = {'name': 'p', 'kind': 'probe', 'describe': 'x', 'measure': {'probe': 'player', 'field': 'x'},
                 'expect': {'op': '>=', 'value': 1}, 'play': {'name': 'thumbs', 'seconds': seconds, 'inputs': list(inputs)}}
            t = task('a' * 40, 'b' * 40, milestones=[{'name': 'm', 'checks': [c]}])
            self.assertEqual(list(vg.check_schema(t, vg.SCHEMAS['game-task'])), [], inputs)
            return vg.task_semantic_errors(t)
        stick = {'t': 1, 'drag': [[0.2, 0.8], [0.3, 0.7]], 'over': 0.5, 'hold': 4}
        jump = {'t': 2, 'tap': {'widget': 'JumpButton'}, 'finger': 1}
        self.assertEqual(errs(stick, jump, {'t': 6, 'tap': [0.5, 0.5]}), [])   # two thumbs; finger 0 again after it lifts
        self.assertEqual(errs({'t': 1, 'tap': [0.5, 0.5]}, {'t': 1.1, 'tap': [0.5, 0.5]}), [])   # the gap itself
        self.assertEqual(errs(stick, {'t': 3, 'tap': [0.5, 0.5]}),
                         ['check p: play thumbs puts finger 0 down at 3 s, less than 0.1 s after it lifts (5.5 s): give '
                          'the second touch another finger, or start it later'])
        self.assertEqual(errs({'t': 1, 'tap': [0.5, 0.5]}, {'t': 1.05, 'tap': [0.5, 0.5]})[0][:50],
                         'check p: play thumbs puts finger 0 down at 1.05 s,')
        self.assertEqual(errs(dict(stick, hold=9)), ['check p: play thumbs has a touch that ends after the play (10 s)'])
        self.assertEqual(errs({'t': 9, 'tap': [0.5, 0.5], 'hold': 2}),
                         ['check p: play thumbs has a touch that ends after the play (10 s)'])
        self.assertEqual(errs({'t': 3, 'key': '<Keyboard>/escape', 'press': True}), [])   # the back button is a key

    def test_required_quality_judges(self):
        """A required judge is noted as one that should be optional, but for the judges of the brief's looks: a `judge`
        named `looks_as_asked` and a `judge` in `still_works`."""
        def judge(name, kind='judge', **over):
            return {'name': name, 'kind': kind, 'question': 'q', 'rubric': [{'key': 'k', 'criterion': 'c'}], **over}
        t = {'milestones': [
            {'name': 'done', 'checks': [judge('looks_as_asked'), judge('reads_well'), judge('optional', required=False),
                                        judge('looks_as_asked', 'code_judge')]},
            {'name': 'still_works', 'checks': [judge('hud_unchanged'), judge('code', 'code_judge')]}]}
        self.assertEqual(vg.required_quality_judges(t), ['reads_well', 'looks_as_asked', 'code'])

    def test_schema_keywords(self):
        """Every keyword the schemas use is one check_schema reads, an annotation, or the if/then/else that
        check_assets_manifest evaluates by hand (a keyword it ignored would be a rule never checked); each works."""
        read = {'type', 'required', 'properties', 'additionalProperties', 'minProperties', 'enum', 'const', 'pattern',
                'minLength', 'maxLength', 'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'items',
                'minItems', 'maxItems', '$ref', 'allOf', 'anyOf', 'oneOf', 'discriminator'}
        notes = {'$schema', '$id', '$defs', '$comment', 'title', 'description', 'default', 'propertyName', 'mapping'}
        used = set()

        def walk(node, names=False):
            if isinstance(node, dict):
                for k, v in node.items():
                    used.update(() if names else (k,))
                    walk(v, not names and k in ('properties', '$defs', 'mapping'))
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        for s in vg.SCHEMAS.values():
            walk(s)
        self.assertEqual(used - read - notes - {'if', 'then', 'else'}, set())
        patterns = []

        def collect(node):
            if isinstance(node, dict):
                patterns.extend(v for k, v in node.items() if k == 'pattern' and isinstance(v, str))
                for v in node.values():
                    collect(v)
            elif isinstance(node, list):
                for v in node:
                    collect(v)
        for s in vg.SCHEMAS.values():
            collect(s)
        for p in patterns:   # what _ecma relies on: a pattern's `$` is its last character, never escaped
            self.assertTrue('$' not in p[:-1] and not p.endswith('\\$'), p)
        self.assertNotEqual(list(vg.check_schema(['-scenario\n'], vg.SCHEMAS['game-task']['properties']['play_args'],
                                                 vg.SCHEMAS['game-task'])), [])
        either = [{'type': 'string'}, {'type': 'integer'}]
        for schema, good, bad in (
                ({'type': 'integer'}, 3, True), ({'type': ['string', 'null']}, None, 3), ({'required': ['a']}, {'a': 1}, {}),
                ({'properties': {'a': {'type': 'string'}}}, {'a': 'x'}, {'a': 1}),
                ({'properties': {'a': {}}, 'additionalProperties': False}, {'a': 1}, {'b': 1}),
                ({'minProperties': 1}, {'a': 1}, {}), ({'enum': ['a', 1]}, 1, True), ({'const': True}, True, 1),
                ({'pattern': '^a+$'}, 'aa', 'ab'), ({'pattern': '^a+$'}, 'aa', 'aa\n'),   # $ ends the string
                ({'pattern': '^\\d$'}, '7', '٧'),                                  # \d is 0-9, as in ECMA-262
                ({'minLength': 1}, 'a', ''), ({'maxLength': 1}, 'a', 'ab'),
                ({'minimum': 0}, 0, -1), ({'maximum': 1}, 1, 2), ({'exclusiveMinimum': 0}, 0.5, 0),
                ({'exclusiveMaximum': 1}, 0.5, 1), ({'items': {'type': 'string'}}, ['a'], ['a', 1]),
                ({'minItems': 1}, [1], []), ({'maxItems': 1}, [1], [1, 2]),
                ({'$defs': {'S': {'type': 'string'}}, '$ref': '#/$defs/S'}, 'a', 1),
                ({'allOf': [{'minimum': 0}, {'maximum': 1}]}, 0.5, 2), ({'anyOf': either}, 'a', None),
                ({'oneOf': [{'minimum': 0}, {'maximum': 1}]}, 5, 0.5),   # 0.5 fits both
                ({'oneOf': either + [{'type': 'number'}], 'discriminator': {'propertyName': 'k'}}, 2, None)):
            self.assertEqual(list(vg.check_schema(good, schema)), [], (schema, good))
            self.assertNotEqual(list(vg.check_schema(bad, schema)), [], (schema, bad))

    def test_workflow_rows_unit(self):
        """workflow.jsonl beyond one row: JSON, seq order, user.direction rows and the links to them, an empty reason
        (a warning), no rows."""
        lines = [workflow_row(1), 'not json', workflow_row(3, seq=1),
                 workflow_row(4, op='user.direction', actor='user', reason_source='user_direction', params={'via': 'x'}),
                 workflow_row(5, direction='kr-00009'), workflow_row(6, reason=' ')]
        rep = vg.Report()
        self.assertEqual(vg.check_workflow(rep, 'w', lines), {'kr-00004'})
        errs = ' | '.join(errors(rep))
        for what in ('line 2: not JSON', 'line 3: seq 1 not after 1', 'line 4: user.direction row needs actor user',
                     'line 5: direction kr-00009 is not an earlier user.direction row'):
            self.assertIn(what, errs)
        self.assertIn(('warning', 'w', '1 row(s) with an empty reason'), rep.items)
        rep = vg.Report()
        vg.check_workflow(rep, 'w', [])
        self.assertEqual(errors(rep), ['no rows'])

    def test_git_log_unit(self):
        """git.log's form: its first line, commit lines, the fields in order, dev_NN authors, ISO dates, each commit
        once, its last commit returned."""
        a, b = 'a' * 40, 'b' * 40

        def entry(sha, author='dev_1', date='2026-11-01T10:00:00+01:00'):
            return [f'commit {sha}', 'Parents: ', f'Author: {author}', f'AuthorDate: {date}', 'Committer: dev_1',
                    'CommitDate: 2026-11-01T10:00:00Z', '', '    A message', '']
        rep = vg.Report()
        self.assertEqual(vg.check_git_log(rep, 'g', io.StringIO('\n'.join(['GIT-LOG 1', '# a header'] + entry(a)))), a)
        self.assertEqual(errors(rep), [])
        bad = ['GIT-LOG 2', 'commit xyz'] + entry(b, 'Jane Doe', 'yesterday') + [f'commit {a}', 'Parents: ', 'Commit: x']
        rep = vg.Report()
        vg.check_git_log(rep, 'g', io.StringIO('\n'.join(bad + entry(b))))
        errs = ' | '.join(errors(rep))
        for what in ('first line must be "GIT-LOG 1"', "bad commit line 'commit xyz'", 'Author "Jane Doe" is not anonymised',
                     'AuthorDate "yesterday" is not ISO 8601', 'expected "Author:" after commit aaaaaaaa',
                     'a commit appears twice'):
            self.assertIn(what, errs)
        rep = vg.Report()
        vg.check_git_log(rep, 'g', io.StringIO('GIT-LOG 1\n'))
        self.assertEqual(errors(rep), ['no commits'])

    def test_dataset_rules_unit(self):
        """A repo Dataset/ folder's cross-file rules, and a zip's one top folder (no git needed)."""
        tmp = tempfile.mkdtemp(prefix='ggfd')
        self.addCleanup(shutil.rmtree, tmp, onerror=onerror)
        ds = os.path.join(tmp, 'Dataset')
        # a line separator inside a string, raw as JSON allows it: one row, as the repo's check reads it
        write(ds, 'workflow.jsonl', workflow_row(1, reason='Create the project').replace('\\u2028', ' ') + '\n')
        write(ds, 'Brief/brief.md', '# Brief\n')
        write(ds, 'History/x.txt', 'x')
        write(ds, 'Tasks/README.md', 'x')
        scenario = {'file': f'Gameplay/{SLUG}_S1.mp4', 'scenario': 1, 'name': 'Rush', 'result': 'win', 'seconds': 30}

        def check(**over):
            m = {'layout': 'godot-dataset-layout/v1', 'game': SLUG, 'title': 'Kiln Run', 'version': '1.0',
                 'commit': 'a' * 40, 'status': 'pending', 'variant': 'repo-dataset', 'pending': ['Gameplay'],
                 'scenarios': [scenario], 'totals': {'files': 5, 'bytes': 0},
                 'files': [{'path': 'workflow.jsonl', 'bytes': 1, 'sha256': '0' * 64},
                           {'path': 'Gone.txt', 'bytes': 1, 'sha256': '0' * 64}],
                 'replay_verification': None, 'build': {'config': 'Release', 'commit': 'a' * 40, 'exe': 'Build/K.exe'},
                 'history': None, 'brief': {'brief': 'Brief/brief.md', 'design': 'Brief/design.md'}, 'tasks': None}
            write(ds, 'manifest.json', json.dumps(dict(m, **over)))
            rep = vg.Report()
            vg.check_dataset(rep, ds, 'dataset')
            return rep, ' | '.join(errors(rep))
        rep, errs = check()
        for what in ('files[] lists Gone.txt, not in the dataset', 'workflow.jsonl: ', 'totals do not match files[]',
                     f'scenario file Gameplay/{SLUG}_S1.mp4 not in files[]', 'variant repo-dataset has build null',
                     'replay_verification is null but ReplayScripts/ is not listed as pending', 'no git.log',
                     'no Brief/design.md', 'Brief/brief.md is nearly empty', 'a repo Dataset/ has no History/',
                     'a repo Dataset/ has no Tasks/'):
            self.assertIn(what, errs)
        self.assertNotIn('not JSON', errs)
        warns = ' | '.join(m for s, a, m in rep.items if s == 'warning')
        self.assertIn('status pending: Gameplay', warns)
        self.assertIn('no user.direction rows', warns)
        rep, errs = check(status='complete', pending=['ReplayScripts'], scenarios=[])
        for what in ('status complete but no ReplayScripts/Verification/report.json', 'status complete with pending entries',
                     'status complete needs replay_verification with pass true or false', 'no scenario videos'):
            self.assertIn(what, errs)
        for cut in ('ReplayScripts/Verification/report.json', 'GodotProject/assets.manifest.json'):
            write(ds, cut, '{"schema": ')   # cut short: an error, never a traceback
        rep, errs = check(variant='full')
        self.assertEqual([a for s, a, m in rep.items if m.startswith('not JSON: ')],
                         ['dataset: report.json', 'dataset: GodotProject/assets.manifest.json'])
        rep, errs = check(platform={'kind': 'tablet'})
        self.assertIn("$.platform.kind: \"tablet\" not one of ['desktop', 'mobile']", errs)
        write(ds, 'manifest.json', 'not json')
        rep = vg.Report()
        vg.check_dataset(rep, ds, 'dataset')
        self.assertTrue(errors(rep)[0].startswith('manifest.json is not JSON'), rep.items)
        z = os.path.join(tmp, 'two.zip')
        with zipfile.ZipFile(z, 'w') as zf:
            zf.writestr('a/manifest.json', '{}')
            zf.writestr('b/x.txt', 'x')
        rep = vg.Report()
        vg.check_dataset(rep, z, 'dataset')
        self.assertEqual(errors(rep), ['the zip must hold exactly one top folder (<game>/)'])

    def test_split_tasks(self):
        """split-tasks.py: the agent's half (everything but milestones, the seed without its reference: play_scene,
        play_args and player included) and the grader's half (milestones, seed.reference), which merge back into the
        task; exit 2 for a file that isn't JSON or whose name isn't its file's."""
        if not os.path.isfile(os.path.join(TOOLS, 'split-tasks.py')):
            self.skipTest('no split-tasks.py')
        tmp = tempfile.mkdtemp(prefix='ggfs')
        self.addCleanup(shutil.rmtree, tmp, onerror=onerror)
        t = task('a' * 40, 'b' * 40)
        write(tmp, f'in/{t["name"]}.json', json.dumps(t))
        write(tmp, 'in/broken.json', '{')
        write(tmp, 'in/other.json', json.dumps(dict(t, name='renamed')))
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'split-tasks.py'), os.path.join(tmp, 'in'),
                            os.path.join(tmp, 'out')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(json.loads(r.stdout), [{'name': t['name'], 'title': t['title'], 'kind': 'bug_fix',
                                                 'difficulty': 'hard'}])
        agent = json.loads(read(os.path.join(tmp, 'out', t['name'], 'task.json')))
        grader = json.loads(read(os.path.join(tmp, 'out', t['name'], 'grader.json')))
        self.assertEqual(sorted(agent), sorted(k for k in t if k != 'milestones'))
        self.assertNotIn('reference', agent['seed'])
        self.assertEqual(grader, {'name': t['name'], 'seed': {'reference': 'b' * 40}, 'milestones': t['milestones']})
        self.assertEqual(dict(agent, milestones=grader['milestones'], seed=dict(agent['seed'], **grader['seed'])), t)

    def test_files_closed(self):
        """Every file the validator reads is closed once read (an open one is a ResourceWarning, which the task try's
        tests make an error): the format files it loads at import, and a repo's assets.manifest.json."""
        tmp = tempfile.mkdtemp(prefix='ggfr')
        self.addCleanup(shutil.rmtree, tmp, onerror=onerror)
        git(tmp, 'init', '-q')
        write(tmp, 'assets.manifest.json', json.dumps({'schema': 'assets-manifest/v1', 'project': 'KilnRun', 'assets': []}))
        write(tmp, 'project.godot', 'config_version=5\n')
        write(tmp, 'Platform.json', '{"platform":"mobile","orientation":"portrait"}\n')
        git(tmp, 'add', 'assets.manifest.json', 'project.godot', 'Platform.json')
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter('always', ResourceWarning)
            again = load('validate_game_again', 'validate-game.py')
            again.check_repo(again.Report(), tmp)
        self.assertEqual([str(w.message) for w in seen if issubclass(w.category, ResourceWarning)], [])

    def test_cli_any_name(self):
        """The findings print whatever the console's code page: a name it lacks (Ω, not in cp1252) is printed, and the
        verdict is the exit code, never a traceback."""
        tmp = tempfile.mkdtemp(prefix='ggfc')
        self.addCleanup(shutil.rmtree, tmp, onerror=onerror)
        repo = os.path.join(tmp, SLUG)
        os.makedirs(repo)
        git(repo, 'init', '-q', '-b', 'main')
        for k, v in (('core.hooksPath', os.path.join(tmp, 'nohooks')), ('commit.gpgsign', 'false')):
            git(repo, 'config', k, v)
        write(repo, 'game/Ω.gd', 'extends Node\n')
        commit(repo, 'A script without its .uid')
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'validate-game.py'), repo, '--quiet'], capture_output=True,
                           env=dict(os.environ, PYTHONIOENCODING='cp1252'))
        self.assertEqual(r.returncode, 2, r.stderr.decode('utf-8', 'replace'))
        self.assertIn('game/Ω.gd: no .uid tracked', r.stdout.decode('utf-8'))

    def test_wildcard_takes_one(self):
        """A select that takes one object by a wildcard name alone is a warning, never an error (a teleport to Coin*
        goes to CoinSpawner); one narrowed by its component, tag or full name is not."""
        def report(teleport, point, first):
            t = task('a' * 40, 'b' * 40)
            checks = t['milestones'][2]['checks']
            checks[0]['measure'] = {'probe': 'player', 'field': 'dist', 'to': {'object': point}, 'agg': 'min'}
            checks[1]['play']['inputs'].append({'t': 9, 'teleport_to': teleport, 'distance': 0.3, 'hold': 0.5})
            checks[2]['measure'] = {'probe': 'objects', 'select': first, 'field': 'speed', 'of': 'first'}
            rep = vg.Report()
            vg.check_task(rep, 'repo: Tasks', 'x', t, SLUG, None)
            self.assertEqual(errors(rep), [])
            return [m for s, a, m in rep.items if s == 'warning']
        ws = report({'name': 'Coin*'}, {'name': 'Lamp*'}, {'name': 'Coin?'})
        self.assertEqual(len(ws), 3, ws)
        staged = [{'t': 3, 'pin': {'name': 'Foe*'}, 'hold': 1}, {'t': 4, 'damage': 5, 'to': {'name': 'Foe*'}},
                  {'t': 5, 'set': 'health', 'on': {'name': 'Foe*'}, 'value': 1},
                  {'t': 6, 'set': 'health', 'on': {'name': 'Crate*'}, 'value': 1, 'all': True}]
        t = task('a' * 40, 'b' * 40)
        t['milestones'][2]['checks'][1]['play']['inputs'].extend(staged)
        self.assertEqual(vg.task_semantic_errors(t), [])
        said = ' | '.join(vg.task_warnings(t))
        for what in ('pin {"name": "Foe*"} holds the nearest', 'damage to {"name": "Foe*"} strikes the nearest',
                     'set on {"name": "Foe*"} is written on the nearest'):
            self.assertIn('play collect: ' + what + ' object whose name fits', said)
        self.assertNotIn('Crate*', said)   # every match is written: none is picked
        for start in ('x: play collect: teleport_to {"name": "Coin*"} goes to the nearest object whose name fits',
                      'x: check hero_on_ground: the point {"object": {"name": "Lamp*"}} stands at the first',
                      'x: check enemies_move: the select {"name": "Coin?"} reads the first'):
            self.assertTrue(any(w.startswith(start) for w in ws), (start, ws))
        self.assertEqual(report({'name': 'Coin*', 'component': 'Coin'}, {'name': 'Lamp_1'},
                                {'name': 'Coin*', 'tag': 'Coin'}), [])
        for key, value in (('effect', True), ('owner', {'tag': 'Yard'}), ('mesh', 'Rock_LOD0'), ('text', '^SCORE'),
                           ('where', [{'prop': 'lit', 'op': '==', 'value': True}])):
            self.assertFalse(vg.wild({'name': 'Smoke*', key: value}), key)   # a select's own narrowing keys
        t = task('a' * 40, 'b' * 40)
        t['milestones'][2]['checks'][2]['measure'] = {'probe': 'components', 'select': {'name': 'Smoke*', 'effect': True},
                                                      'field': 'active', 'of': 'first'}
        self.assertEqual(vg.task_warnings(t), [])

    def test_schema_first(self):
        """A task the schema refuses gets the schema's errors, never a traceback from the rules that read its values."""
        t = task('a' * 40, 'b' * 40)
        t['milestones'][2]['checks'][0]['weight'] = '3'
        t['milestones'][2]['checks'][1]['measure']['select']['rect'] = ['a', 0, 1, 1]
        t['milestones'][3]['checks'][0]['name'] = ['hero_moves']
        rep = vg.Report()
        self.assertFalse(vg.check_task(rep, 'repo: Tasks', 'x', t, SLUG, None))
        self.assertTrue(errors(rep), rep.items)
        rep = vg.Report()
        self.assertTrue(vg.check_task(rep, 'repo: Tasks', 'x', task('a' * 40, 'b' * 40), SLUG, None))
        self.assertEqual(errors(rep), [])

    def test_a_union_with_a_tag_reports_the_shape_its_tag_names(self):
        """A check is told apart by its kind and a measure by its probe: a missing or unknown tag says so and lists
        the ones there are, and anything else is the named shape's own problem, at its own path."""
        def problems(change):
            t = task('a' * 40, 'b' * 40)
            change(t['milestones'][2]['checks'][1])
            return list(vg.check_schema(t, vg.SCHEMAS['game-task']))
        at = '$.milestones[2].checks[1]'
        self.assertEqual(problems(lambda c: c.pop('kind')), [f'{at}: missing "kind"'])
        (wrong,) = problems(lambda c: c.update(kind='probes'))
        self.assertTrue(wrong.startswith(f'{at}.kind: "probes" not one of [') and "'build'" in wrong
                        and "'probe'" in wrong, wrong)
        self.assertEqual(problems(lambda c: c['measure'].pop('probe')), [f'{at}.measure: missing "probe"'])
        (refused,) = problems(lambda c: c['measure'].update(probe='actors'))
        self.assertTrue(refused.startswith(f'{at}.measure.probe: "actors" not one of [') and "'objects'" in refused,
                        refused)
        self.assertEqual(problems(lambda c: c['measure'].update(sample=1)),
                         [f'{at}.measure: unexpected key "sample"'], "the measure's own shape, never 'matches none'")
        self.assertEqual(problems(lambda c: None), [])


# ---- the task schema as the validator's rules need it ------------------------------------------------------------------
def probe_check(measure, play='look', expect=None):
    return {'name': 'p', 'kind': 'probe', 'describe': 'x', 'play': play, 'measure': measure,
            'expect': expect or {'op': '>=', 'calibrate': 0.5}}


class Schema(unittest.TestCase):
    S = vg.SCHEMAS['game-task']
    KINDS = ('player', 'camera', 'objects', 'components', 'widgets', 'ui', 'screen', 'spawns', 'log', 'audio',
             'render', 'world')   # the probe kinds
    MEASURE = {kind: ref.split('/')[-1]
               for kind, ref in S['$defs']['Probe']['properties']['measure']['discriminator']['mapping'].items()}
    SHAPE = {kind: ref.split('/')[-1]   # the check kinds' definitions
             for kind, ref in S['$defs']['Milestone']['properties']['checks']['items']['discriminator']['mapping'].items()}
    RUBRIC = [{'key': 'k', 'criterion': 'x'}]
    # a valid check of each kind, given its name and kind where it is used
    CHECKS = {'build': {}, 'boot': {'seconds': 60}, 'package': {}, 'log_absent': {'pattern': 'Error'},
              'file_exists': {'glob': '*.gd'}, 'judge': {'question': 'q', 'rubric': RUBRIC},
              'code_judge': {'question': 'q', 'rubric': RUBRIC},
              'probe': probe_check({'probe': 'log', 'pattern': 'Error'})}
    # every character a play argument (one at its 60) and a scene's path may hold
    ARGS = ['-Level=Yard_2', '--seed:7,8', '-config/night.cfg', 'X', 'x' * 60]
    SCENE = 'res://scenes/Town_2-b.Night (1).tscn'

    def ok(self, value, ref):
        return list(vg.check_schema(value, self.S['$defs'][ref], self.S))

    def test_kinds(self):
        """The probe kinds and the check kinds are the ones the validator's rules are written for; a kind the format
        has not is refused by name."""
        self.assertEqual(sorted(self.MEASURE), sorted(self.KINDS))
        self.assertEqual(sorted(self.SHAPE), sorted(self.CHECKS))
        extra = {'objects': {'select': {'component': 'Enemy'}}, 'components': {'select': {'component': 'Light3D'}},
                 'widgets': {'select': {'component': 'Slider'}}, 'spawns': {'component': 'Projectile'},
                 'log': {'pattern': 'Error'}}
        fields = {'player': 'y', 'camera': 'yaw', 'objects': 'count', 'components': 'count', 'widgets': 'count',
                  'ui': 'count', 'screen': 'luminance', 'spawns': 'spawned', 'log': 'count', 'audio': 'count',
                  'render': 'draw_calls', 'world': 'time_scale'}
        for probe in self.KINDS:
            measure = dict({'probe': probe, 'field': fields[probe]}, **extra.get(probe, {}))
            self.assertEqual(self.ok(probe_check(measure, 'look', {'op': '>=', 'value': 1}), 'Probe'), [], probe)
        for refused in ('pieces', 'light', 'grading', 'ground', 'drawn', 'asset', 'trace', 'actors'):
            self.assertNotEqual(self.ok(probe_check({'probe': refused, 'field': 'count'}), 'Probe'), [], refused)
        for play in ('editor', 'trace'):
            self.assertNotEqual(self.ok(probe_check({'probe': 'player', 'field': 'y'}, play), 'Probe'), [], play)
        for field in ('draw_calls', 'triangles', 'texture_mb'):   # a budget: a number of its own, a literal value
            c = probe_check({'probe': 'render', 'field': field, 'agg': 'max'}, 'look', {'op': '<=', 'value': 700})
            self.assertEqual(self.ok(c, 'Probe'), [], field)
            self.assertEqual(vg.probe_errors(c, {'commit': 'a'}, 'b', {}), [], field)

    def test_touch_inputs(self):
        play = {'name': 'thumbs', 'seconds': 30, 'inputs': [
            {'t': 1, 'tap': [0.5, 0.5]}, {'t': 2, 'tap': {'widget': 'Jump*'}, 'hold': 0.5, 'finger': 1},
            {'t': 3, 'drag': [[0.2, 0.8], {'widget': 'Stick'}, [0.4, 0.6]], 'over': 0.5, 'hold': 2, 'finger': 0},
            {'t': 9, 'key': '<Keyboard>/escape', 'press': True}]}
        self.assertEqual(self.ok(play, 'TaskPlay'), [])
        for bad in ({'t': 1, 'tap': [1.5, 0.5]}, {'t': 1, 'tap': [0.5]}, {'t': 1, 'tap': [0.5, 0.5], 'finger': 10},
                    {'t': 1, 'drag': [[0.5, 0.5]]}, {'t': 1, 'tap': {'widget': 'Hud/Jump'}},
                    {'t': 1, 'tap': [0.5, 0.5], 'hold': 0}, {'t': 9, 'key': 'Android_Back', 'press': True}):
            self.assertNotEqual(self.ok(dict(play, inputs=[bad]), 'TaskPlay'), [], bad)

    def test_sounds_that_start(self):
        near = {'near': {'point': {'object': {'tag': 'door'}}, 'radius': 3}, 'sound_class': 'SFX'}
        for field in ('started', 'started_audible', 'sounds', 'repeats'):   # how many started: a literal value
            c = probe_check({'probe': 'audio', 'select': near, 'field': field, 'window': [2, 3]}, 'look',
                            {'op': '>=', 'value': 1})
            self.assertEqual(self.ok(c, 'Probe'), [], field)
            self.assertEqual(vg.probe_errors(c, {'commit': 'a'}, 'b', {}), [], field)
        self.assertNotEqual(self.ok(probe_check({'probe': 'audio', 'field': 'takes'}), 'Probe'), [])
        for field in ('sounds', 'repeats'):   # one reading of the whole window: nothing to aggregate
            c = probe_check({'probe': 'audio', 'field': field, 'agg': 'sum'}, 'look', {'op': '>=', 'value': 1})
            self.assertEqual(vg.probe_errors(c, {'commit': 'a'}, 'b', {}),
                             [f"check p: an audio measure's {field} is read from the names of the sounds that started in "
                              'its window: it takes no `agg`'])
        banded = dict(near, near={'point': {'xyz': [0, 0, 0]}, 'radius': 3, 'y_min': 2, 'y_max': 1})
        c = probe_check({'probe': 'audio', 'select': banded, 'field': 'started'}, 'look', {'op': '>=', 'value': 1})
        self.assertEqual(vg.probe_errors(c, {'commit': 'a'}, 'b', {}), ['check p: a near band has y_min < y_max'])

    def test_contact_stages(self):
        live = {'tag': 'foe', 'where': [{'prop': 'dead', 'op': '==', 'value': False}]}
        play = {'name': 'duel', 'seconds': 12, 'inputs': [
            {'t': 1, 'set': 'health', 'on': {'tag': 'foe'}, 'value': 1, 'all': True},
            {'t': 1, 'set': 'Health.current', 'on': {'player': True}, 'value': 500},
            {'t': 2, 'pin': live, 'hold': 3, 'front': 1.5},
            {'t': 2, 'pin': {'player': False, 'component': 'CollisionObject3D', 'has': {'visible': True},
                             'near': {'point': {'player': True}, 'radius': 6}}, 'hold': 1,
             'at': {'object': {'component': 'Flare'}}, 'offset': [0, 0.5, 0]},
            {'t': 2.3, 'key': '<Keyboard>/j', 'press': True},
            {'t': 3, 'damage': 20, 'to': {'player': True}},
            {'t': 4, 'damage': 5, 'to': live, 'from': {'name': 'Turret'}}]}
        self.assertEqual(self.ok(play, 'TaskPlay'), [])
        for bad in ({'t': 1, 'pin': live}, {'t': 1, 'pin': live, 'hold': 0}, {'t': 1, 'pin': live, 'hold': 1, 'front': -1},
                    {'t': 1, 'damage': 0, 'to': live}, {'t': 1, 'damage': 5}, {'t': 1, 'set': 'items[0]', 'on': live, 'value': 1},
                    {'t': 1, 'set': 'health', 'on': live}, {'t': 1, 'set': 'health', 'on': live, 'value': [1]}):
            self.assertNotEqual(self.ok(dict(play, inputs=[bad]), 'TaskPlay'), [], bad)
        for field in ('frozen', 'damage_taken'):
            c = probe_check({'probe': 'objects', 'select': live, 'field': field, 'of': 'max', 'agg': 'max'}, play,
                            {'op': '>=', 'value': 0.05})
            self.assertEqual(self.ok(c, 'Probe'), [], field)
        self.assertNotEqual(self.ok(probe_check({'probe': 'objects', 'select': live, 'field': 'focus_player'}), 'Probe'), [])
        for field in ('time_scale', 'flow', 'paused'):
            c = probe_check({'probe': 'world', 'field': field, 'window': [2, 3], 'agg': 'min'}, play, {'op': '<', 'value': 1})
            self.assertEqual(self.ok(c, 'Probe'), [], field)
            self.assertEqual(vg.probe_errors(c, {'commit': 'a'}, 'b', {}), [], field)
        self.assertNotEqual(self.ok(probe_check({'probe': 'world', 'field': 'time_dilation'}), 'Probe'), [])

        def errs(*inputs):
            c = probe_check({'probe': 'player', 'field': 'x'}, {'name': 'duel', 'seconds': 12, 'inputs': list(inputs)},
                            {'op': '>=', 'value': 1})
            self.assertEqual(self.ok(c, 'Probe'), [], inputs)
            return vg.probe_errors(c, {'commit': 'a'}, 'b', {})
        self.assertEqual(errs(*play['inputs']), [])
        self.assertEqual(errs({'t': 1, 'pin': {'player': True}, 'hold': 2}),
                         ['check p: play duel pins the player: a pin holds another object (a teleport holds the player)'])
        self.assertEqual(errs({'t': 1, 'pin': live, 'hold': 2, 'front': 1, 'at': {'player': True}}),
                         ['check p: play duel pins an object `front` of the player or `at` a point, not both'])

    def test_task_level(self):
        S = self.S
        t = task('a' * 40, 'b' * 40)
        self.assertEqual(list(vg.check_schema(t, S)), [])
        self.assertEqual(S['properties']['engine']['const'], 'godot-4.7')
        for bad in ({'engine': '4.7'}, {'engine': 'godot-4.3'}, {'play_scene': 'scenes/Main.tscn'},
                    {'play_scene': 'res://scenes/Main.txt'}, {'play_args': ['-scenario', 'two words']},
                    {'play_args': ['x'] * 17}, {'play_args': ['-' + 'x' * 61]}, {'play_args': ['x' * 61]},
                    {'player': {'class': 'Hero'}}, {'play_map': 'res://scenes/Main.tscn'}):
            self.assertNotEqual(list(vg.check_schema(dict(t, **bad), S)), [], bad)
        for good in ({'play_scene': None, 'play_args': []}, {'play_scene': 'res://scenes/Level (2).tscn'},
                     {'play_args': ['-x'] * 16}, {'play_scene': self.SCENE, 'play_args': self.ARGS},
                     {'player': {'name': 'Hero', 'component': 'HeroController'}}, {'player': None}):
            self.assertEqual(list(vg.check_schema(dict(t, **good), S)), [], good)
        self.assertEqual(vg.task_semantic_errors(t), [])

    def test_check_names_its_kind(self):
        """A check without `kind` passed (build, boot and package take a name alone, and the checks' discriminator hides a
        second match) and the checker then had no kind to run it by: every check names its kind, with no default."""
        for kind, rest in self.CHECKS.items():
            check = dict(rest, name='c', kind=kind)
            self.assertEqual(self.ok({'name': 'm', 'checks': [check]}, 'Milestone'), [], kind)
            del check['kind']
            self.assertNotEqual(self.ok({'name': 'm', 'checks': [check]}, 'Milestone'), [], kind)
            self.assertNotIn('default', self.S['$defs'][self.SHAPE[kind]]['properties']['kind'], kind)


# ---- a game's platform --------------------------------------------------------------------------------------------------
def mobile_files(orientation):
    """(project.godot, export_presets.cfg) of a mobile game as templates/new-game.ps1 -Platform mobile fills them in."""
    size = vg.PHONE_SIZE[orientation]
    project = template('project.godot', MOBILE_TEMPLATE)
    for mark, value in (('__PHONE_WIDTH__', size[0]), ('__PHONE_HEIGHT__', size[1]),
                        ('__HANDHELD__', vg.ORIENTATIONS.index(orientation))):
        project = project.replace(mark, str(value))
    return project, template('export_presets.cfg', MOBILE_TEMPLATE)


class Platform(unittest.TestCase):
    """read_platform, the one reader of Platform.json, and its command line face."""

    def folder(self, text=None):
        d = tempfile.mkdtemp(prefix='ggfm')
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        if text is not None:
            write(d, 'Platform.json', text)
        return d

    def test_the_reader(self):
        self.assertIsNone(vg.read_platform(self.folder()))
        self.assertEqual(vg.platform_of(self.folder()), {'platform': 'desktop'})
        d = self.folder(json.dumps({'platform': 'mobile', 'orientation': 'portrait'}))
        self.assertEqual(vg.read_platform(d), 'portrait')
        self.assertEqual(vg.platform_of(d), {'platform': 'mobile', 'orientation': 'portrait', 'width': 1080, 'height': 1920})
        self.assertEqual(vg.platform_of(self.folder('\ufeff{"platform": "mobile", "orientation": "landscape"}')),
                         {'platform': 'mobile', 'orientation': 'landscape', 'width': 1920, 'height': 1080})
        for bad in ('{"platform": "desktop"}', '{"platform": "mobile"}', 'not json', '["mobile", "portrait"]', '',
                    '{"platform": "mobile", "orientation": "sideways"}',
                    '{"platform": "mobile", "orientation": "portrait", "tablet": true}'):
            with self.assertRaises(ValueError, msg=bad):
                vg.read_platform(self.folder(bad))
            with self.assertRaises(ValueError, msg=bad):
                vg.platform_said(bad)

    def test_the_reader_from_the_command_line(self):
        tool = os.path.join(TOOLS, 'validate-game.py')
        r = subprocess.run([sys.executable, tool, '--platform', self.folder()], capture_output=True, text=True)
        self.assertEqual((r.returncode, json.loads(r.stdout)), (0, {'platform': 'desktop'}))
        r = subprocess.run([sys.executable, tool, '--platform', self.folder('{"platform":"mobile","orientation":"landscape"}\n')],
                           capture_output=True, text=True)
        self.assertEqual(json.loads(r.stdout), {'platform': 'mobile', 'orientation': 'landscape', 'width': 1920, 'height': 1080})
        self.assertEqual(len(r.stdout.splitlines()), 1)
        r = subprocess.run([sys.executable, tool, '--platform', self.folder('{"platform": "mobile"}')], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (2, ''))
        self.assertIn('Platform.json must be', r.stderr)

    def test_the_cli_needs_nothing_but_the_folder(self):
        """--platform answers from a copy of the script alone: no format file, no schema, no git."""
        d = self.folder('{"platform":"mobile","orientation":"landscape"}\n')
        alone = os.path.join(d, 'validate-game.py')
        shutil.copy(os.path.join(TOOLS, 'validate-game.py'), alone)
        r = subprocess.run([sys.executable, alone, '--platform', d], capture_output=True, text=True)
        self.assertEqual((r.returncode, json.loads(r.stdout), r.stderr),
                         (0, {'platform': 'mobile', 'orientation': 'landscape', 'width': 1920, 'height': 1080}, ''))

    def test_the_sizes_a_game_is_played_at(self):
        size = vg.SPEC['repo']['platform']['size']
        self.assertEqual(size['desktop'], {'width': 1920, 'height': 1080})
        self.assertEqual({k: (v['width'], v['height']) for k, v in size['mobile'].items()}, vg.PHONE_SIZE)
        self.assertEqual({k: (v['width'], v['height']) for k, v in vg.load_json(
            os.path.join(REPO, 'docs', 'dataset-layout-v1.json'))['gameplay_video']['mobile'].items()}, vg.PHONE_SIZE)


class Mobile(unittest.TestCase):
    """Rule `mobile`: a mobile game's project settings and its Android preset, and a mobile dataset's manifest; a
    desktop game is not looked at."""

    def game(self, platform=None, project=None, presets=None):
        d = tempfile.mkdtemp(prefix='ggfm')
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        if platform is not None:
            write(d, 'Platform.json', platform if isinstance(platform, str) else json.dumps(platform))
        for name, text in (('project.godot', project), ('export_presets.cfg', presets)):
            if text is not None:
                write(d, name, text)
        return d

    def said(self, d, files=('Platform.json',)):
        rep = vg.Report()
        vg.check_mobile(rep, d, list(files))
        return [m.replace(self.KEEP, '') for sev, area, m in rep.items if area == 'mobile' and sev == 'error']

    KEEP = ' (godot-mobile-game skill, "Start": the project settings stay as new-game.ps1 made them)'

    def test_a_desktop_game_is_not_looked_at(self):
        self.assertEqual(self.said(self.game(project=template('project.godot'), presets=template('export_presets.cfg')),
                                   files=()), [])
        self.assertEqual(self.said(self.game(), files=()), [])

    def test_the_template_passes_for_both_orientations(self):
        for orientation in ('landscape', 'portrait'):
            project, presets = mobile_files(orientation)
            self.assertNotIn('__', project + presets)
            self.assertEqual(vg.mobile_project_errors(orientation, project), [], orientation)
            self.assertEqual(vg.mobile_preset_errors(presets), [], orientation)
            d = self.game({'platform': 'mobile', 'orientation': orientation}, project, presets)
            self.assertEqual(self.said(d), [])
            rep = vg.Report()
            vg.check_mobile(rep, d, ['Platform.json'])
            self.assertEqual([m for s, a, m in rep.items if s == 'note'],
                             [f'an Android phone game held in {orientation}: the project settings agree with Platform.json'])
        self.assertEqual(vg.godot_config(mobile_files('portrait')[1])['preset.1.options']['package/unique_name'],
                         'com.kilnrun.game')

    def test_each_project_setting_that_disagrees_is_named(self):
        project, _ = mobile_files('portrait')

        def errs(old, new, orientation='portrait'):
            self.assertIn(old, project)
            return vg.mobile_project_errors(orientation, project.replace(old, new))
        self.assertEqual(errs('x', 'x', 'landscape'),
                         ['display/window/size is 1080x1920, but Platform.json says landscape (1920x1080)',
                          'display/window/handheld/orientation=1 (portrait), but Platform.json says landscape'])
        self.assertIn('handheld/orientation=6 (sensor),', errs('handheld/orientation=1', 'handheld/orientation=6')[0])
        self.assertEqual(errs('handheld/orientation=1', 'handheld/orientation=5'), [])     # sensor portrait: held one way
        self.assertIn('orientation=0 (landscape)', errs('window/handheld/orientation=1\n', '')[0])   # the engine's default
        self.assertEqual(errs('renderer/rendering_method="mobile"', 'renderer/rendering_method="forward_plus"'),
                         ['rendering/renderer/rendering_method="forward_plus": a mobile game uses the Mobile renderer '
                          '("mobile"), never the desktop renderer'])
        self.assertIn('rendering_method="forward_plus"', errs('renderer/rendering_method="mobile"\n', '')[0])   # default
        self.assertEqual(errs('renderer/rendering_method.mobile="mobile"\n', ''), [])       # default "mobile"
        self.assertIn('rendering_method.mobile="gl_compatibility"',
                      errs('rendering_method.mobile="mobile"', 'rendering_method.mobile="gl_compatibility"')[0])
        self.assertIn('import_etc2_astc is not true', errs('import_etc2_astc=true\n', '')[0])   # default false
        self.assertIn('quit_on_go_back is not false', errs('config/quit_on_go_back=false\n', '')[0])   # default true
        self.assertIn('stretch/mode="disabled"', errs('window/stretch/mode="canvas_items"\n', '')[0])   # the default
        self.assertEqual(errs('pointing/emulate_mouse_from_touch=true\n', ''), [])            # default true
        self.assertIn('emulate_mouse_from_touch is not true',
                      errs('emulate_mouse_from_touch=true', 'emulate_mouse_from_touch=false')[0])
        self.assertIn('emulate_touch_from_mouse is not false',
                      errs('emulate_touch_from_mouse=false', 'emulate_touch_from_mouse=true')[0])
        self.assertIn('display/window/size is 1152x648', errs('window/size/viewport_width=1080\n'
                                                              'window/size/viewport_height=1920\n', '')[0])

    def test_each_preset_setting_that_disagrees_is_named(self):
        _, presets = mobile_files('portrait')

        def errs(old, new):
            self.assertIn(old, presets)
            return vg.mobile_preset_errors(presets.replace(old, new))
        self.assertEqual(errs('name="Android"', 'name="Phone"'), ['no preset named "Android"'])
        self.assertIn('use_gradle_build is not true', errs('use_gradle_build=true', 'use_gradle_build=false')[0])
        self.assertIn('use_gradle_build is not true', errs('gradle_build/use_gradle_build=true\n', '')[0])   # default false
        self.assertIn('architectures/arm64-v8a is not true', errs('arm64-v8a=true', 'arm64-v8a=false')[0])
        self.assertEqual(errs('architectures/arm64-v8a=true\n', ''), [])                     # default true
        self.assertEqual(errs('architectures/x86_64=false', 'architectures/x86_64=true'),
                         ['architectures/x86_64 is true: a mobile game is built for arm64 alone'])
        self.assertEqual(errs('gradle_build/min_sdk="26"', 'gradle_build/min_sdk="24"'), ['gradle_build/min_sdk=24: at least 26'])
        self.assertEqual(errs('gradle_build/target_sdk="34"', 'gradle_build/target_sdk="33"'),
                         ['gradle_build/target_sdk=33: at least 34'])
        self.assertEqual(errs('gradle_build/min_sdk="26"', 'gradle_build/min_sdk=""'), [])   # the engine's own: 29
        self.assertEqual(errs('gradle_build/target_sdk="34"\n', ''), [])                     # the engine's own: 36
        self.assertIn("the Android package name is 'com.example.$genname': com.<project in lower case>.game",
                      errs('package/unique_name="com.kilnrun.game"\n', '')[0])               # the engine's default
        self.assertIn("package name is 'org.kiln.run'", errs('"com.kilnrun.game"', '"org.kiln.run"')[0])
        self.assertIn("package name is 'com.kiln_run.game'", errs('"com.kilnrun.game"', '"com.kiln_run.game"')[0])
        self.assertIn("for the platform 'iOS'", errs('platform="Android"', 'platform="iOS"')[0])

    def test_a_platform_file_that_says_neither_is_an_error_never_desktop(self):
        project, presets = mobile_files('portrait')
        for bad in ('{"platform": "desktop"}', '{"platform": "mobile"}', 'not json',
                    '{"platform": "mobile", "orientation": "sideways"}'):
            self.assertEqual(len(self.said(self.game(bad, project, presets))), 1, bad)

    def test_an_uncommitted_platform_file_and_missing_settings_are_named(self):
        project, presets = mobile_files('portrait')
        mobile = {'platform': 'mobile', 'orientation': 'portrait'}
        self.assertIn('not committed', self.said(self.game(mobile, project, presets), files=())[0])
        self.assertEqual(self.said(self.game(mobile)),
                         ['no project.godot (templates/new-game.ps1 -Platform mobile writes it)',
                          'no export_presets.cfg (templates/new-game.ps1 -Platform mobile writes it)'])
        self.assertEqual(self.said(self.game(mobile, project, template('export_presets.cfg'))),
                         ['export_presets.cfg: no preset named "Android"'])

    def test_the_rule_is_one_of_the_games_rules(self):
        project, presets = mobile_files('landscape')
        d = self.game({'platform': 'mobile', 'orientation': 'portrait'}, project, presets)
        rep = vg.Report()
        vg.check_rules(rep, d, ['Platform.json'])
        self.assertTrue(errors(rep, 'mobile'))

    # ---- the mobile template -------------------------------------------------------------------------------------------
    def test_the_overlay_uses_only_the_placeholders_new_game_fills(self):
        new_game = read(os.path.join(REPO, 'templates', 'new-game.ps1'))
        used = set()
        for d, _, files in os.walk(MOBILE_TEMPLATE):
            for f in files:
                used |= set(re.findall(r'__[A-Z_]+?__', read(os.path.join(d, f)) + f))
        for name in used:
            self.assertIn(f"'{name}'", new_game)
        self.assertLessEqual({'__ORIENTATION__', '__PORTRAIT__', '__PHONE_WIDTH__', '__PHONE_HEIGHT__', '__ANDROID_NAME__'}, used)
        self.assertIn("[ValidateSet('desktop', 'mobile')][string]$Platform = 'desktop'", new_game)
        self.assertIn("[ValidateSet('landscape', 'portrait')][string]$Orientation", new_game)

    # ---- a mobile dataset's manifest ---------------------------------------------------------------------------------
    class View:
        def __init__(self, platform_json=None):
            self.text = platform_json

        def open_text(self, rel):
            if self.text is None:
                raise KeyError(rel)
            return io.StringIO(self.text)

    APK = {'apk': 'KilnRun.apk', 'package': 'com.kilnrun.game', 'version_code': 1, 'version_name': '1.0', 'min_sdk': 26,
           'target_sdk': 34}

    def platform(self, manifest, platform_json=None, files=('Build/KilnRun.apk',)):
        rep = vg.Report()
        m = dict({'variant': 'full', 'build': {'config': 'Release', 'exe': 'Build/KilnRun.exe'}}, **manifest)
        vg.check_dataset_platform(rep, 'dataset', self.View(platform_json), m, set(files))
        return errors(rep), [msg for sev, _, msg in rep.items if sev == 'warning']

    def test_a_desktop_dataset_says_nothing_of_a_platform(self):
        self.assertEqual(self.platform({}), ([], []))
        self.assertEqual(self.platform({'platform': {'kind': 'desktop'}}), ([], []))
        self.assertIn('desktop game', self.platform({'build': dict(self.APK, exe='Build/KilnRun.exe')})[0][0])
        self.assertIn('says mobile, portrait', self.platform({}, '{"platform": "mobile", "orientation": "portrait"}')[0][0])

    def test_a_mobile_dataset_agrees_with_its_project_and_names_its_apk(self):
        mobile = {'platform': {'kind': 'mobile', 'orientation': 'portrait'}}
        held = '{"platform": "mobile", "orientation": "portrait"}'
        self.assertEqual(self.platform(dict(mobile, build=dict(self.APK, exe='Build/KilnRun.exe')), held), ([], []))
        found, warned = self.platform(mobile, held)
        self.assertEqual(found, [])
        self.assertIn('without its APK', warned[0])
        self.assertIn('there is no GodotProject/Platform.json', self.platform(mobile)[0][0])
        self.assertIn('says mobile, landscape', self.platform(mobile, held.replace('portrait', 'landscape'))[0][0])
        self.assertIn('says its orientation', self.platform({'platform': {'kind': 'mobile'}}, held)[0][0])
        self.assertIn('GodotProject/Platform.json must be', self.platform(mobile, '{"platform": "desktop"}')[0][0])
        for change, why in (({'min_sdk': 24}, 'minSdk 24'), ({'package': 'com.Company.Product'}, 'package name'),
                            ({'apk': 'Other.apk'}, 'not in files[]')):
            build = dict(self.APK, exe='Build/KilnRun.exe', **change)
            self.assertIn(why, self.platform(dict(mobile, build=build), held)[0][0], change)
        del build['target_sdk']
        self.assertIn('without target_sdk', self.platform(dict(mobile, build=dict(build, apk='KilnRun.apk')), held)[0][0])

    def test_the_manifest_schema_takes_a_platform_and_an_apk(self):
        schema = vg.SCHEMAS['dataset-manifest']['properties']
        self.assertEqual(list(vg.check_schema({'kind': 'mobile', 'orientation': 'portrait'}, schema['platform'])), [])
        self.assertTrue(list(vg.check_schema({'kind': 'phone'}, schema['platform'])))
        build = dict(self.APK, config='Release', commit='a' * 40, exe='Build/KilnRun.exe')
        self.assertEqual(list(vg.check_schema(build, schema['build'], vg.SCHEMAS['dataset-manifest'])), [])
        self.assertTrue(list(vg.check_schema(dict(build, apk='Build/KilnRun.apk'), schema['build'], vg.SCHEMAS['dataset-manifest'])))
        self.assertNotIn('platform', vg.SCHEMAS['dataset-manifest']['required'])


# ---- the game contract and the sound rule ------------------------------------------------------------------------------
class Rules(unittest.TestCase):
    """Rules `contract` and `sound` on a game's own GDScript."""

    def said(self, files, autoload=None):
        d = tempfile.mkdtemp(prefix='ggfk')
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        for rel, text in files.items():
            write(d, rel, text)
        write(d, 'project.godot', 'config_version=5\n\n[autoload]\n\nAutoPlay="*res://addons/autoplay/autoplay.gd"\n'
              + ''.join(f'{name}="*res://{path}"\n' for name, path in (autoload or {}).items()))
        rep = vg.Report()
        vg.check_contract(rep, d, list(files) + ['project.godot'])
        vg.check_sound(rep, d, list(files) + ['project.godot'])
        return [(a, m.replace(vg.REQUIRED, '')) for s, a, m in rep.items if s == 'error'], \
               [m for s, a, m in rep.items if s == 'note']

    HURT = ('extends CharacterBody3D\n\n@export var max_health: float = 10.0\nvar health := 10.0\n\n'
            'func take_damage(amount: float, source: Node) -> float:\n\thealth -= amount\n\treturn amount\n')
    HIT = 'extends Area3D\n\nfunc _on_body_entered(body: Node) -> void:\n\tbody.take_damage(2.0, self)\n'

    def test_a_game_without_combat_is_not_held_to_the_damage_rule(self):
        errs, notes = self.said({'game/menu.gd': 'extends Control\n\nvar health_bar: ProgressBar\n'
                                                 'var healthy_label = $Label\nvar title := "Health"\n'})
        self.assertEqual(errs, [])
        self.assertEqual(notes, ['no combat (no health member, no hit function): the damage rule does not apply'])

    def test_combat_through_take_damage_passes(self):
        errs, notes = self.said({'game/enemy.gd': self.HURT, 'game/spike.gd': self.HIT})
        self.assertEqual((errs, notes), ([], []))

    def test_combat_without_the_method_or_its_call_is_named(self):
        own = 'extends Node\n\nvar hp: int = 3\n\nfunc apply_damage(n: int) -> void:\n\thp -= n\n'
        errs, _ = self.said({'game/enemy.gd': own})
        self.assertEqual(len(errs), 2, errs)
        self.assertTrue(errs[0][1].startswith('combat without a take_damage method: what can be hurt has `func '
                                              'take_damage(amount: float, source: Node) -> float`'), errs)
        self.assertIn("the game's own hit function apply_damage at game/enemy.gd:5", errs[0][1])
        self.assertTrue(errs[1][1].startswith('combat without a call of take_damage'), errs)
        untyped = self.HURT.replace('amount: float, source: Node) -> float', 'amount, source)')
        errs, _ = self.said({'game/enemy.gd': untyped, 'game/spike.gd': self.HIT})
        self.assertEqual(len(errs), 1, errs)       # the method without its types is not the contract's
        errs, _ = self.said({'game/enemy.gd': self.HURT.replace('source: Node', 'source: Node3D = null')})
        self.assertEqual([m[:36] for _, m in errs], ['combat without a call of take_damage'])

    def test_key_state_in_a_static_var_or_an_autoload_is_named(self):
        errs, _ = self.said({'game/enemy.gd': self.HURT + '\nstatic var lives: int = 3\nstatic var hit_sound_volume := 1.0\n'
                                                          'static var count := 0\n',
                             'game/spike.gd': self.HIT,
                             'game/run.gd': 'extends Node\n\nenum Phase { CALM, STORM }\nvar phase: Phase = Phase.CALM\n'
                                            'var is_dead = false\nvar best_time := 0.0\nvar state_name := "calm"\n'
                                            '\nfunc reset() -> void:\n\tvar health = 3\n'},
                            autoload={'Run': 'game/run.gd'})
        self.assertEqual(errs, [
            ('contract', 'game/enemy.gd:10: lives (combat state) is a static var: keep it on a node instance in the '
                         'scene, where a probe reads it'),
            ('contract', 'game/run.gd:4: phase (phase or state) is in the autoload Run: keep it on a node instance in '
                         'the scene, where a probe reads it'),
            ('contract', 'game/run.gd:5: is_dead (combat state) is in the autoload Run: keep it on a node instance in '
                         'the scene, where a probe reads it')])

    def test_the_factorys_own_scripts_and_comments_are_not_the_games(self):
        own = 'extends Node\nstatic var health := 1.0\nfunc deal_damage():\n\tpass\n'
        errs, notes = self.said({'addons/autoplay/autoplay.gd': own, 'addons/task_probe/task_probe.gd': own,
                                 'steps/bake.gd': own + 'var s = AudioStreamWAV.new()\n',
                                 'game/notes.gd': 'extends Node\n# static var health := 1.0\n'
                                                  'var hint := "func deal_damage(): AudioStreamGenerator"\n'
                                                  '"""\nstatic var hp = 1\n"""\nvar after := 1\n'})
        self.assertEqual(errs, [])
        self.assertEqual(len(notes), 1)

    def test_a_sound_made_at_run_time_is_named(self):
        errs, _ = self.said({'game/synth.gd': 'extends AudioStreamPlayer\n\nfunc _ready() -> void:\n'
                                              '\tvar wav := AudioStreamWAV.new()\n\tstream = wav\n',
                             'game/tone.gd': 'extends Node\nvar playback: AudioStreamGeneratorPlayback\n',
                             'scenes/Beep.tscn': '[gd_scene format=3]\n\n[sub_resource type="AudioStreamGenerator" '
                                                 'id="gen"]\n\n[node name="Beep" type="AudioStreamPlayer"]\n',
                             'scenes/Hit.tscn': '[gd_scene format=3]\n\n[ext_resource type="AudioStream" '
                                                'path="res://assets/hit.wav" id="1"]\n'})
        self.assertEqual(sorted(errs), [
            ('sound', 'game/synth.gd:4: AudioStreamWAV.new makes a sound at run time: import every sound as an audio '
                      'file (a clip, or a WAV a committed step script made), so it has a name'),
            ('sound', 'game/tone.gd:2: AudioStreamGenerator makes a sound at run time: import every sound as an audio '
                      'file (a clip, or a WAV a committed step script made), so it has a name'),
            ('sound', 'scenes/Beep.tscn:3: AudioStreamGenerator makes a sound at run time: import every sound as an '
                      'audio file (a clip, or a WAV a committed step script made), so it has a name')])

    def test_rules_only_cli(self):
        d = tempfile.mkdtemp(prefix='ggfk')
        self.addCleanup(shutil.rmtree, d, onerror=onerror)
        git(d, 'init', '-q')
        write(d, 'game/enemy.gd', 'extends Node\nvar hp: int = 3\n')
        write(d, 'Platform.json', '{"platform": "phone"}')
        git(d, 'add', '-A')
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'validate-game.py'), d, '--rules-only'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith('INVALID  3 error(s)'), r.stdout)
        for what in ('x contract: combat without a take_damage method', 'x contract: combat without a call',
                     'x mobile: Platform.json must be'):
            self.assertIn(what, r.stdout)


# ---- the dataset ----------------------------------------------------------------------------------------------------
@unittest.skipUnless(HAS_LFS, 'git-lfs is not installed')
class Dataset(Base):
    def make_zip(self, mutate=None):
        self.made = getattr(self, 'made', 0) + 1   # a test may make several
        repo, ds = self.repo, os.path.join(self.tmp, f'ds{self.n}_{self.made}', SLUG)
        head = git(repo, 'rev-parse', 'HEAD')
        log = ['GIT-LOG 1']
        for line in git(repo, 'log', '--reverse', '--format=%H|%P|%an|%aI|%cn|%cI|%s').splitlines():
            h, p, an, ad, cn, cd, s = line.split('|')
            log += [f'commit {h}', f'Parents: {p}', f'Author: {an}', f'AuthorDate: {ad}', f'Committer: {cn}',
                    f'CommitDate: {cd}', '', f'    {s}', '']
        write(ds, 'git.log', '\n'.join(log) + '\n')
        shutil.copy(os.path.join(repo, 'workflow.jsonl'), os.path.join(ds, 'workflow.jsonl'))
        write(ds, 'Brief/brief.md', '# Brief\n\n' + 'Build a small kiln game. ' * 20)
        write(ds, 'Brief/design.md', '# Design\n\n' + 'Systems, scenes and scenarios. ' * 20)
        os.makedirs(os.path.join(ds, 'History'))
        git(repo, 'bundle', 'create', os.path.join(ds, 'History', f'{SLUG}.bundle'), 'main')
        lfs_bytes = n_lfs = 0
        for d, _, fs in os.walk(os.path.join(repo, '.git', 'lfs', 'objects')):
            for f in fs:
                if re.fullmatch(r'[0-9a-f]{64}', f):
                    write(ds, f'History/lfs/objects/{f[:2]}/{f[2:4]}/{f}', read(os.path.join(d, f), 'rb'))
                    n_lfs += 1
                    lfs_bytes += os.path.getsize(os.path.join(d, f))
        tasks_src = os.path.join(self.tmp, f'tasks{self.n}_{self.made}')
        os.makedirs(tasks_src)
        names = sorted(f'{SLUG}-{n}' for n in TASKS)
        for name in names:
            write(tasks_src, f'{name}.json', git(repo, 'show', f'tasks:Tasks/{name}.json'))
        subprocess.run([sys.executable, os.path.join(TOOLS, 'split-tasks.py'), tasks_src, os.path.join(ds, 'Tasks')],
                       check=True, capture_output=True)
        write(ds, 'Tasks/README.md', '# Tasks\n')
        for f in vg.git_ls(repo):
            write(ds, 'GodotProject/' + f, read(os.path.join(repo, f), 'rb'))
        write(ds, 'Build/KilnRun.exe', b'MZ' + b'\0' * 30)
        write(ds, 'Screenshots/hero.jpg', read(os.path.join(repo, 'Docs/screenshots/hero.jpg'), 'rb'))
        write(ds, f'Gameplay/{SLUG}_S1.mp4', b'\0\0\0\x18ftypmp42' + b'\0' * 64)   # a full delivery has a gameplay video
        sections = ['Requirements', 'Package contents', 'Play the game', 'Replay the creation process',
                    'Restore the git history', 'Tasks', 'Scenarios', 'Screenshots', 'Assets and licences', 'Integrity']
        write(ds, 'README.md', '# Kiln Run\n\nThis delivery is pending.\n\n' + ''.join(
            f'## {s}\n\n' + ('![hero](Screenshots/hero.jpg)\n\n' if s == 'Screenshots' else
                             f'1. Rush: Gameplay/{SLUG}_S1.mp4\n\n' if s == 'Scenarios' else 'Text.\n\n') for s in sections))
        m = {'layout': 'godot-dataset-layout/v1', 'game': SLUG, 'title': 'Kiln Run', 'version': '1.0', 'commit': head,
             'status': 'pending', 'variant': 'full', 'pending': ['ReplayScripts'],
             'scenarios': [{'file': f'Gameplay/{SLUG}_S1.mp4', 'scenario': 1, 'name': 'Rush', 'result': 'win', 'seconds': 30}],
             'replay_verification': None,
             'build': {'config': 'Release', 'commit': head, 'exe': 'Build/KilnRun.exe'},
             'history': {'bundle': f'History/{SLUG}.bundle', 'head': head,
                         'commits': int(git(repo, 'rev-list', '--count', 'main')), 'refs': ['refs/heads/main'],
                         'lfs_objects': n_lfs, 'lfs_bytes': lfs_bytes, 'authors_anonymised': True},
             'brief': {'brief': 'Brief/brief.md', 'design': 'Brief/design.md'},
             'tasks': {'count': len(names), 'names': names, 'schema': 'game-task/1'}}
        if mutate:
            mutate(m, ds)
        files = []
        for d, _, fs in os.walk(ds):
            for f in fs:
                rel = os.path.relpath(os.path.join(d, f), ds).replace('\\', '/')
                if rel.startswith('History/lfs/objects/'):
                    continue
                data = read(os.path.join(d, f), 'rb')
                files.append({'path': rel, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        m.update(files=files, totals={'files': len(files), 'bytes': sum(f['bytes'] for f in files)})
        write(ds, 'manifest.json', json.dumps(m, indent=1))
        z = os.path.join(repo, 'Dataset.pending.zip')
        with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
            for d, _, fs in os.walk(ds):
                for f in fs:
                    full = os.path.join(d, f)
                    zf.write(full, SLUG + '/' + os.path.relpath(full, ds).replace('\\', '/'))
        return z

    def said(self, mutate=None):
        rep = vg.Report()
        vg.check_dataset(rep, self.make_zip(mutate), 'dataset')
        return errors(rep)

    def test_valid_dataset(self):
        z = self.make_zip()
        rep = vg.Report()
        vg.check_dataset(rep, z, 'dataset')
        self.assertEqual(errors(rep), [])
        notes = ' '.join(m for s, a, m in rep.items)
        self.assertIn('5 task(s)', notes)
        self.assertIn('LFS objects referenced', notes)
        if shutil.which('powershell') or shutil.which('pwsh'):
            # The layout check probes gameplay videos with the ffprobe it finds: the machine root's pinned ffmpeg, else
            # PATH. A scratch root keeps the machine's ffmpeg away from the stub video above (the probe is then noted
            # as skipped); an ffprobe on PATH would still probe the stub, which is no video.
            if shutil.which('ffprobe'):
                self.skipTest('an ffprobe on PATH would probe the stub gameplay video')
            with unittest.mock.patch.dict(os.environ, {'GGF_ROOT': self.tmp, 'GGF_CONFIG': os.path.join(self.tmp, 'none.json')}):
                rep = vg.Report()
                vg.run_layout_validator(rep, z, False)
            self.assertEqual(errors(rep), [])
            self.assertTrue(any('PENDING' in m for s, a, m in rep.items), rep.items)

    def test_dataset_errors(self):
        def mutate(m, ds):
            m['tasks']['count'] = 2
            shutil.rmtree(os.path.join(ds, 'Tasks', f'{SLUG}-{TASKS[1]}'))   # four tasks left, two of them medium
            for n, level in ((TASKS[2], 'medium'), (TASKS[3], None)):
                g = os.path.join(ds, 'Tasks', f'{SLUG}-{n}', 'task.json')
                t = dict(json.loads(read(g)), difficulty=level)
                write(ds, os.path.relpath(g, ds).replace('\\', '/'), json.dumps({k: v for k, v in t.items() if v is not None}))
            g = os.path.join(ds, 'Tasks', f'{SLUG}-fix-hero-hud', 'task.json')
            t = json.loads(read(g))
            t['milestones'] = []
            write(ds, os.path.relpath(g, ds).replace('\\', '/'), json.dumps(t))
            shutil.rmtree(os.path.join(ds, 'GodotProject', 'assets', 'third_party', 'kenney'))
            with open(os.path.join(ds, 'workflow.jsonl'), 'a', encoding='utf-8') as f:
                f.write(workflow_row(3, reason='Asked Claude to tidy the HUD') + '\n')
            os.remove(os.path.join(ds, 'GodotProject', 'project.godot'))
        rep = vg.Report()
        z = self.make_zip(mutate)
        vg.check_dataset(rep, z, 'dataset')
        errs = ' | '.join(errors(rep))
        for what in ("holds the grader's half (milestones)", 'manifest tasks (count, names) differ',
                     'banned name (?i)\\bclaude\\b x1', 'Tasks/: 4 task(s): a game ships at least 5',
                     f'Tasks/: 2 hard task(s): a game needs at least 4 hard tasks (medium: {SLUG}-{TASKS[3]}, {SLUG}-{TASKS[2]})'):
            self.assertIn(what, errs)
        self.assertIn('listed asset file not present: Crates: assets/third_party/kenney/', errs)
        if shutil.which('powershell') or shutil.which('pwsh'):
            rep = vg.Report()
            vg.run_layout_validator(rep, z, False)
            self.assertIn('GodotProject/ has no project.godot at its top', errors(rep))

    def test_gameplay_pending(self):
        """A game without a gameplay video is rejected: a full delivery never lists Gameplay/ as pending (a pending
        ReplayScripts/ stays allowed, as test_valid_dataset has it)."""
        def mutate(m, ds):
            shutil.rmtree(os.path.join(ds, 'Gameplay'))
            m.update(pending=['ReplayScripts', 'Gameplay'], scenarios=[])
        self.assertEqual(self.said(mutate), ['Gameplay/ is pending: a game is rejected without a gameplay video; record '
                                             'a scenario of the release commit and package again'])

    def test_a_mobile_dataset(self):
        """A mobile game's dataset: Platform.json in GodotProject/, the platform in the manifest, the APK beside the
        Windows player; without the APK a warning."""
        def mobile(m, ds, apk=True):
            write(ds, 'GodotProject/Platform.json', '{"platform":"mobile","orientation":"portrait"}\n')
            m['platform'] = {'kind': 'mobile', 'orientation': 'portrait'}
            if apk:
                write(ds, 'Build/KilnRun.apk', b'PK\3\4' + b'\0' * 30)
                m['build'].update(apk='KilnRun.apk', package='com.kilnrun.game', version_code=1, version_name='1.0',
                                  min_sdk=26, target_sdk=34)
        self.assertEqual(self.said(mobile), [])
        rep = vg.Report()
        vg.check_dataset(rep, self.make_zip(lambda m, ds: mobile(m, ds, apk=False)), 'dataset')
        self.assertEqual(errors(rep), [])
        self.assertTrue(any('a mobile game without its APK in Build/' in m for s, a, m in rep.items if s == 'warning'))

    def test_the_manifests_platform_is_the_projects(self):
        def said_desktop(m, ds):
            write(ds, 'GodotProject/Platform.json', '{"platform":"mobile","orientation":"portrait"}\n')
        self.assertEqual(self.said(said_desktop), ['platform says a desktop game, but GodotProject/Platform.json says mobile, portrait'])

        def said_mobile(m, ds):
            m['platform'] = {'kind': 'mobile', 'orientation': 'landscape'}
        self.assertIn('platform says mobile, landscape, but there is no GodotProject/Platform.json (a desktop game)',
                      self.said(said_mobile))

        def bad_file(m, ds):
            write(ds, 'GodotProject/Platform.json', '{"platform": "desktop"}')
        self.assertTrue(self.said(bad_file)[0].startswith('GodotProject/Platform.json must be'))

        def desktop_held(m, ds):
            m['platform'] = {'kind': 'desktop', 'orientation': 'landscape'}
        self.assertEqual(self.said(desktop_held),
                         ['platform: a mobile game says its orientation (landscape or portrait), a desktop game has none'])

    def test_cli_with_zip(self):
        self.make_zip()
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'validate-game.py'), self.repo, '--no-layout'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
