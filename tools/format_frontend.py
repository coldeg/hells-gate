"""Format readable card sources; optional development tool, never a runtime dependency."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
try:
    import jsbeautifier
except ImportError:
    # I also support the workspace-local installation without global Python changes.
    for parent in ROOT.parents:
        candidate=parent/'.tools/hells-gate-dev'
        if (candidate/'jsbeautifier').is_dir():
            sys.path.insert(0,str(candidate))
            break
    import jsbeautifier


if __name__=='__main__':
    options=jsbeautifier.default_options()
    options.indent_size=2
    options.wrap_line_length=100
    for path in (ROOT/'frontend/src').glob('*.js'):
        path.write_text(jsbeautifier.beautify(path.read_text(encoding='utf-8'),options)+'\n',encoding='utf-8')
    print('FRONTEND_SOURCES_FORMATTED')
