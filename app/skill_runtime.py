"""Run the locally installed de-ai-flavor package, never a simulated validator."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

def package_dir():
    candidates=[]
    cli=shutil.which('de-ai-flavor.cmd') or shutil.which('de-ai-flavor')
    if cli:
        candidates.append(Path(cli).parent/'node_modules'/'de-ai-flavor')
        candidates.append(Path(cli).resolve().parent.parent)
    if os.environ.get('APPDATA'):
        candidates.append(Path(os.environ['APPDATA'])/'npm/node_modules/de-ai-flavor')
    for path in candidates:
        if (path/'bin/cli.js').is_file() and (path/'SKILL.md').is_file():
            return path
    raise ValueError('未找到 npm skill，请执行 npm install -g de-ai-flavor')

def info():
    try:
        p=package_dir()
        version=json.loads((p/'package.json').read_text(encoding='utf-8'))['version']
        return dict(installed=True,version=version,engine='本地 npm CLI',path=str(p))
    except ValueError as e:
        return dict(installed=False,message=str(e))

def validate(text):
    path=package_dir()
    node=shutil.which('node')
    if not node:
        raise ValueError('未找到 Node.js，无法执行本地质检')
    with tempfile.TemporaryDirectory(prefix='articleflow-skill-') as directory:
        source=Path(directory)/'article.txt'
        source.write_text(text,encoding='utf-8')
        try:
            result=subprocess.run([node,str(path/'bin/cli.js'),'--file',str(source),'--json'],capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        except subprocess.TimeoutExpired:
            raise ValueError('npm skill 检测超时') from None
    marker='--- JSON 输出 ---'
    if result.returncode!=0 or marker not in result.stdout:
        raise ValueError('npm skill 未返回有效检测结果')
    try:
        report=json.loads(result.stdout.split(marker,1)[1].strip())
        if not isinstance(report['summary']['passed'],bool):
            raise ValueError()
    except (ValueError,KeyError,TypeError):
        raise ValueError('npm skill 返回的 JSON 无效') from None
    report['engine']=info()
    return report
