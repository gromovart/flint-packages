"""Export committed package trees as immutable local install tags; no network."""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ('skills', 'subagents', 'hooks', 'workflows', 'connection')
def git(*args, input=None):
    return subprocess.run(['git', *args], cwd=ROOT, input=input, text=True,
                          check=True, capture_output=True).stdout.strip()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', args.version):
        parser.error('Use a release version such as 1.0.0')
    if git('status', '--porcelain'):
        parser.error('Commit or remove local changes first')
    tags = ['demo-' + family + '-v' + args.version for family in FAMILIES]
    existing = set(git('tag', '--list').splitlines())
    if existing.intersection(tags):
        parser.error('Release tag already exists; publish a new version')
    head = git('rev-parse', 'HEAD')
    trees = [git('rev-parse', head + ':packages/demo/' + family) for family in FAMILIES]
    # Preflight every package version before creating any ref.
    for family in FAMILIES[:-1]:
        manifest = git('show', head + ':packages/demo/' + family + '/package.yaml')
        if '  version: ' + args.version not in manifest.splitlines():
            parser.error('Manifest version differs from release: ' + family)
    commits = [git('commit-tree', tree, '-p', head, input='Export ' + tag + '\n')
               for tree, tag in zip(trees, tags)]
    # A single update-ref transaction creates every tag or none.
    commands = 'start\n' + ''.join('create refs/tags/' + tag + ' ' + commit + '\n'
                                     for tag, commit in zip(tags, commits)) + 'prepare\ncommit\n'
    git('update-ref', '--stdin', input=commands)
    print('Created local tags:\n' + '\n'.join(tags))

if __name__ == '__main__':
    main()
