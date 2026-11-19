"""The documents against the repo: every relative link, repo path, script name, option and section reference leads
somewhere, and every skill loads by its front matter. Plain text checks: no engine, no network, no git history.

    python -m unittest discover -s tools/tests -p "test_docs.py" -v

What is not checked, so a green run does not claim it: the JSON examples of the documents (the task check's own tests
and the probe tests hold the formats), and a script's positional arguments.
"""
import os, re, subprocess, unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(TOOLS)

PROBES = 'docs/task-probes.md'
SKILL = 'skills/godot-write-tasks/SKILL.md'


def read(rel):
    with open(os.path.join(REPO, rel), encoding='utf-8') as f:
        return f.read()


def tracked():
    """The repo's files: git's list (with the files not yet added), else the tree (an export has no .git)."""
    r = subprocess.run(['git', '-C', REPO, '-c', 'core.quotepath=off', 'ls-files', '--cached', '--others',
                        '--exclude-standard'], capture_output=True)
    if r.returncode == 0 and r.stdout.strip():
        return [p for p in r.stdout.decode('utf-8', 'replace').split('\n') if p and os.path.isfile(os.path.join(REPO, p))]
    out = []
    for base, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in ('.git', '.local', '__pycache__', '.godot', 'Logs')]
        out += [os.path.relpath(os.path.join(base, f), REPO).replace(os.sep, '/') for f in files]
    return out


# ---- text ---------------------------------------------------------------------------------------------------------
FENCE = re.compile(r'^[ \t]*```(\w*)[ \t]*\n(.*?)^[ \t]*```[ \t]*$', re.S | re.M)
HEADING = re.compile(r'^(#{1,6})[ \t]+(.*?)[ \t]*$', re.M)


def line_of(text, pos):
    return text.count('\n', 0, pos) + 1


def prose(text):
    """The text with its fenced blocks blanked: every character keeps its place."""
    return FENCE.sub(lambda m: re.sub(r'[^\n]', ' ', m.group(0)), text)


def sections(text):
    """The section numbers of a document's headings ("2.4", "5")."""
    out = set()
    for m in HEADING.finditer(prose(text)):
        num = re.match(r'(\d+(?:\.\d+)*)\.?(?=\s|$)', m.group(2))
        if num:
            out.add(num.group(1))
    return out


def anchors(text):
    """The anchors of a document's headings, as GitHub makes them."""
    out = set()
    for m in HEADING.finditer(prose(text)):
        title = re.sub(r'`|\*|\[([^\]]*)\]\([^)]*\)', lambda x: x.group(1) or '', m.group(2))
        out.add(re.sub(r'[^\w\- ]', '', title.lower()).replace(' ', '-'))
    return out


# ---- links, paths, script names --------------------------------------------------------------------------------------
LINK = re.compile(r'(?<!\!)\[[^\]\n]*\]\(([^)\s]+)\)')
ROOTS = ('tools', 'docs', 'skills', 'machine', 'templates')
PATH = re.compile(r'(?<![\w<>%\\/.-])((?:' + '|'.join(ROOTS) + r')[/\\][\w./\\-]*\w)')
UNDER_ROOT = re.compile(r'(?:<GGF_ROOT>|%GGF_ROOT%|<root>|<checkout>)[/\\](?:godot-game-factory[/\\])?((?:' + '|'.join(ROOTS)
                        + r')[/\\][\w./\\-]*\w)')
SCRIPT = re.compile(r'(?<![\w/\\.<>-])([A-Za-z][\w-]*\.(?:py|ps1))\b')
# Names a document may use that are no file of this repo: what a machine has under <root>\tools (the installed copies
# of the limiter, its resolver and the engine pin, the ffmpeg folder), the file of reviewed hits a person keeps for the
# packager, and another factory's limiters and hooks.
ON_A_MACHINE = re.compile(r'^tools[/\\](godot-heavy\.ps1|ggf-root\.ps1|godot\.json|ffmpeg-[\w.-]+|package-reviewed-hits\.tsv)')
NOT_OURS = {'ue-heavy.ps1', 'unity-heavy.ps1', 'record-action.ps1', 'record-unity-action.ps1'}


def in_repo(path, files):
    return path in files or any(f.startswith(path.rstrip('/') + '/') for f in files)


def link_problems(rel, text, files, anchor_of):
    """[(line, target, problem)] for the relative links of one markdown file."""
    out = []
    body = prose(text)
    for m in LINK.finditer(body):
        target = m.group(1)
        if re.match(r'[a-z][a-z0-9+.-]*:', target):
            continue
        path, _, frag = target.partition('#')
        dest = os.path.normpath(os.path.join(os.path.dirname(rel), path)).replace(os.sep, '/') if path else rel
        line = line_of(body, m.start())
        if not in_repo(dest, files):
            out.append((line, target, f'{dest} is not in the repo'))
        elif frag and dest.endswith('.md') and frag not in anchor_of(dest):
            out.append((line, target, f'{dest} has no heading "#{frag}"'))
    return out


def path_problems(text, files):
    """[(line, path, problem)] for the repo paths and script names a document names."""
    out, names = [], {f.rsplit('/', 1)[-1] for f in files}
    for rx in (PATH, UNDER_ROOT):
        for m in rx.finditer(text):
            p = m.group(1).replace('\\', '/').rstrip('.')
            rest = re.match(r'[^\s`)]*', text[m.end():]).group(0)
            if '<' in rest or '*' in rest or ON_A_MACHINE.match(m.group(1)):
                continue        # a pattern (docs/briefs/games/<slug>.md, machine/get-*.ps1), a machine's own file
            if not in_repo(p, files):
                out.append((line_of(text, m.start()), m.group(1), f'{p} is not in the repo'))
    body = prose(text)
    for m in SCRIPT.finditer(body):
        name = m.group(1)
        if name not in names and name not in NOT_OURS and not re.fullmatch(r'(x|make_\w+|my[\w-]*)\.(py|ps1)', name):
            out.append((line_of(body, m.start()), name, f'no file of the repo is named {name}'))
    return out


# ---- options ---------------------------------------------------------------------------------------------------------
def python_options(source):
    """The options an argparse parser in `source` declares (hidden ones left out)."""
    return {m.group(1) for m in re.finditer(r'add_argument\(\s*[\'"](--[a-z][a-z-]*)[\'"]([^\n]*)', source)
            if 'SUPPRESS' not in m.group(2)}


def powershell_parameters(source):
    """The parameters of a script's param block, lower case."""
    at = re.search(r'^param\s*\(', source, re.M)
    if not at:
        return set()
    depth, end = 0, len(source)
    for i in range(at.end() - 1, len(source)):
        depth += {'(': 1, ')': -1}.get(source[i], 0)
        if depth == 0:
            end = i
            break
    block = re.sub(r'#[^\n]*', '', source[at.end():end])
    return {m.group(1).lower() for m in re.finditer(r'(?:^|[\],(\s])\$([A-Za-z]\w*)\s*(?==|,|$)', block, re.M)}


OPTION = re.compile(r'(?<![\w-])(--[a-z][a-z-]*)')
FLAG = re.compile(r'(?<![\w-])-([A-Z][A-Za-z]+)\b')
PY_TOOLS = {'task-check.py': 'tools/task_check/cli.py', 'task-try.py': 'tools/task_check/trial.py',
            'validate-game.py': 'tools/validate-game.py', 'thread-stats.py': 'tools/thread-stats.py',
            'package-dataset.py': 'tools/package-dataset.py', 'godot_replay.py': 'tools/godot-replay/godot_replay.py',
            'split-tasks.py': 'tools/split-tasks.py', 'scrub-workflow-rows.py': 'tools/scrub-workflow-rows.py'}


def option_problems(text, files):
    """[(line, option, problem)] for the options shown after a tool's name on its line: a Python tool's `--option`, a
    PowerShell script's `-Parameter` (up to the next script, the end of the code span or a `--`)."""
    scripts = {}
    for f in files:
        if f.endswith('.ps1'):
            scripts.setdefault(f.rsplit('/', 1)[-1], []).append(f)
    out = []
    for i, row in enumerate(text.split('\n'), 1):
        for tool, source in PY_TOOLS.items():
            if tool in row:
                have = python_options(read(source))
                rest = row.split(tool, 1)[1]
                rest = re.split(r'[\w-]+\.(?:py|ps1)\b', rest)[0]
                out += [(i, o, f'{tool} has no option {o}') for o in OPTION.findall(rest) if o not in have]
        for m in re.finditer(r'([A-Za-z][\w-]*\.ps1)\b([^`\n]*)', row):
            name, rest = m.group(1), re.split(r'\s--\s|[\w-]+\.(?:py|ps1)\b', m.group(2))[0]
            if name not in scripts:
                continue
            have = set().union(*(powershell_parameters(read(f)) for f in scripts[name]))
            out += [(i, '-' + flag, f'{name} has no parameter -{flag}') for flag in FLAG.findall(rest)
                    if flag.lower() not in have]
    return out


# ---- section references -------------------------------------------------------------------------------------------------
SECTION_REF = re.compile(r'\bsections?\s+(\d+(?:\.\d+)*)(?:\s*(?:,|and|to|-)\s*(\d+(?:\.\d+)*))?')
NAMED = (('task-probes', PROBES), ('godot-write-tasks', SKILL), ('task-check.md', 'docs/task-check.md'),
         ('autoplay-contract', 'docs/autoplay-contract.md'), ('contract section', 'docs/autoplay-contract.md'),
         ('CONTRACT.md', 'tools/task_check/CONTRACT.md'), ('godot-replay.md', 'docs/godot-replay.md'))


def section_ref_problems(rel, text, numbers_of):
    """[(line, reference, problem)] for every "section N.M": a section of the document the sentence names just
    before it, else of this document."""
    out = []
    body = prose(text)
    flat = body.replace('\n', ' ')   # a reference may wrap; every character keeps its place
    for m in SECTION_REF.finditer(flat):
        before = flat[max(0, m.start() - 80):m.start()]
        named = [(before.rfind(word), doc) for word, doc in NAMED if word in before]
        doc = max(named)[1] if named else rel
        for num in filter(None, m.groups()):
            if num not in numbers_of(doc):
                out.append((line_of(body, m.start()), m.group(0), f'{doc} has no section {num}'))
    return out


# ---- a skill's front matter ---------------------------------------------------------------------------------------------
def frontmatter_problems(folder, text):
    m = re.match(r'---\n(.*?)\n---\n', text, re.S)
    if not m:
        return ['no front matter between two "---" lines at the top']
    rows = m.group(1).split('\n')
    keys = [r.split(':', 1)[0] for r in rows]
    out = [] if keys == ['name', 'description'] else [f'keys {keys}: a skill has name, then description, nothing else']
    name = rows[0].split(':', 1)[1].strip() if rows else ''
    if name != folder:
        out.append(f'name {name!r} is not its folder {folder!r}')
    d = rows[1].split(':', 1)[1].strip() if len(rows) > 1 else ''
    if not re.fullmatch(r"'(?:[^']|'')*'", d):
        out.append("description is not one single-quoted YAML scalar on one line (a quote inside it is written '')")
    elif len(d[1:-1].replace("''", "'")) > 1024:
        out.append(f'description is {len(d[1:-1].replace(chr(39) * 2, chr(39)))} characters, more than 1024')
    return out


# ---- the documents ------------------------------------------------------------------------------------------------------
def show(rel, problems):
    return '\n' + '\n'.join(f'  {rel}:{line}: {str(what)[:160]}\n      {problem}' for line, what, problem in problems)


class Documents(unittest.TestCase):
    """Every tracked markdown file but the art-style catalogue, which names no file or tool of the repo."""

    @classmethod
    def setUpClass(cls):
        cls.files = set(tracked())
        cls.docs = sorted(f for f in cls.files if f.endswith('.md'))
        cls.own = [f for f in cls.docs if not f.startswith('docs/art-styles/')]
        cls.cache = {}

    def text(self, rel):
        if rel not in self.cache:
            self.cache[rel] = read(rel) if os.path.isfile(os.path.join(REPO, rel)) else ''
        return self.cache[rel]

    def test_links(self):
        for rel in self.docs:
            with self.subTest(doc=rel):
                problems = link_problems(rel, self.text(rel), self.files, lambda d: anchors(self.text(d)))
                self.assertFalse(problems, show(rel, problems))

    def test_paths(self):
        for rel in self.own:
            with self.subTest(doc=rel):
                problems = path_problems(self.text(rel), self.files)
                self.assertFalse(problems, show(rel, problems))

    def test_options(self):
        for rel in self.own:
            with self.subTest(doc=rel):
                problems = option_problems(self.text(rel), self.files)
                self.assertFalse(problems, show(rel, problems))

    def test_section_references(self):
        for rel in self.own:
            with self.subTest(doc=rel):
                problems = section_ref_problems(rel, self.text(rel), lambda d: sections(self.text(d)))
                self.assertFalse(problems, show(rel, problems))

    def test_skills_front_matter(self):
        skills = [f for f in self.docs if re.fullmatch(r'skills/[^/]+/SKILL\.md', f)]
        self.assertEqual(len(skills), 6)
        for rel in skills:
            with self.subTest(skill=rel):
                self.assertEqual(frontmatter_problems(rel.split('/')[1], self.text(rel)), [])


class TheChecksCanFail(unittest.TestCase):
    """Each check on a text with the fault it is for."""

    FILES = {'docs/a.md', 'tools/validate-game.py', 'tools/x/run.ps1'}

    def test_links(self):
        text = '# One\n[ok](a.md#one) [gone](b.md) [no heading](a.md#two) [web](https://example.org)\n'
        found = link_problems('docs/a.md', text, self.FILES, lambda d: anchors(text))
        self.assertEqual([t for _, t, _ in found], ['b.md', 'a.md#two'])

    def test_paths(self):
        found = path_problems('`tools/validate-game.py`, `tools/gone.py`, `<root>\\tools\\godot-heavy.ps1`, `lost.ps1`',
                              self.FILES)
        self.assertEqual([p for _, p, _ in found], ['tools/gone.py', 'lost.ps1'])

    def test_options(self):
        self.assertEqual(powershell_parameters('param(\n  [string]$Game,\n  # why\n  [switch]$Force,\n  $Seed = 0\n)\n$x = 1'),
                         {'game', 'force', 'seed'})
        self.assertIn('--platform', python_options(read('tools/validate-game.py')))
        found = option_problems('`python tools/validate-game.py --platform x --nope`', self.FILES)
        self.assertEqual([o for _, o, _ in found], ['--nope'])

    def test_section_references(self):
        found = section_ref_problems('docs/a.md', '## 1. One\nsee section 1 and\nsection 2.3\n', lambda d: {'1'})
        self.assertEqual([p for _, _, p in found], ['docs/a.md has no section 2.3'])

    def test_front_matter(self):
        good = "---\nname: a-skill\ndescription: 'It''s one line.'\n---\n# A\n"
        self.assertEqual(frontmatter_problems('a-skill', good), [])
        self.assertTrue(frontmatter_problems('b-skill', good))
        self.assertTrue(frontmatter_problems('a-skill', good.replace("'It''s one line.'", 'It is: two')))


class OwnerRules(unittest.TestCase):
    """Rules the owner decided (2026-11-19) that the skills must keep saying, in plain text."""

    def test_a_touch_never_names_a_control_the_thread_creates(self):
        mobile = read('skills/godot-mobile-game/SKILL.md')
        self.assertNotIn('A task taps a control by its node name', mobile)
        self.assertNotIn('Touch a control by its name or the caption', mobile)
        for rel in ('skills/godot-mobile-game/SKILL.md', SKILL, PROBES):
            text = ' '.join(read(rel).split())
            self.assertIn('seed.commit', text, rel)
            self.assertRegex(text, r"never (one|a name|by a name)[^.]*(thread|reference)", rel)

    def test_a_short_span_warns_and_never_rejects(self):
        text = ' '.join(read(SKILL).split())
        self.assertIn('The size of the span is a soft bar', text)
        self.assertIn('it warns and never rejects', text)
        self.assertNotIn('the validator enforces the numbers', text)

    def test_no_skill_tells_the_agent_to_go_on_without_the_person(self):
        for rel in sorted(f for f in tracked() if f.startswith('skills/') and f.endswith('.md')):
            text = ' '.join(read(rel).split()).lower()
            self.assertNotIn('never stall', text, rel)
            self.assertNotIn('when the person is away', text, rel)


if __name__ == '__main__':
    unittest.main()
