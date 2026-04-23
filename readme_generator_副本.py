#!/usr/bin/env python3
"""
GitHub README 一键生成工具
输入本地项目路径或 GitHub 仓库链接，自动生成符合开源规范的专业 README.md

用法:
    python readme_generator.py ./my_project
    python readme_generator.py ./my_project -o README.md
    python readme_generator.py https://github.com/owner/repo
    python readme_generator.py https://github.com/owner/repo --branch main
"""

import argparse
import sys
import os
import re
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

try:
    import requests
except ImportError:
    print("❌ 缺少 requests 库，请运行: pip install requests")
    sys.exit(1)

try:
    import git
except ImportError:
    print("❌ 缺少 GitPython 库，请运行: pip install GitPython")
    sys.exit(1)


# ===================== 配置区 =====================
DEFAULT_MODEL = "claude-sonnet-4-6"
GITHUB_API = "https://api.github.com"
DEFAULT_BRANCH = "main"
IGNORED_DIRS = {
    '__pycache__', '.git', '.pytest_cache', '.mypy_cache', '.tox',
    'node_modules', '.venv', 'venv', 'env', '.env', 'dist', 'build',
    '.eggs', '*.egg-info', '.idea', '.vscode', '.DS_Store', 'vendor',
    'coverage', '.coverage', '.circleci', '.github', '.gitlab', 'tmp'
}
IGNORED_FILES = {
    '.gitignore', '.dockerignore', '.editorconfig', '*.pyc', '*.pyo',
    '*.so', '*.dylib', '*.exe', '*.dll', '*.class', '*.jar', '*.war'
}
# ===================== 配置区 =====================


@dataclass
class ProjectInfo:
    """项目信息容器"""
    name: str = ""
    description: str = ""
    language: str = ""
    author: str = ""
    license: str = ""
    homepage: str = ""
    repository_url: str = ""
    readme_content: str = ""
    requirements: List[str] = field(default_factory=list)
    setup_py: str = ""
    pyproject_toml: str = ""
    package_json: str = ""
    cargo_toml: str = ""
    go_mod: str = ""
    structure: List[str] = field(default_factory=list)
    core_files: Dict[str, str] = field(default_factory=dict)
    entry_points: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)


class GitHubRepoParser:
    """解析 GitHub 仓库"""

    @staticmethod
    def parse_url(repo_url: str) -> Tuple[str, str, str]:
        """解析 GitHub URL，返回 (owner, repo, branch)"""
        url = repo_url.replace("https://github.com/", "").replace("http://github.com/", "")
        url = url.replace("www.", "").rstrip("/")

        # 处理分支指定
        branch = DEFAULT_BRANCH
        if "@" in url:
            parts = url.split("@")
            url = parts[0]
            branch = parts[1]

        # 处理 .git 后缀
        url = url.rstrip(".git")

        parts = url.split("/")
        if len(parts) < 2:
            raise ValueError(f"无效的 GitHub 仓库 URL: {repo_url}")
        return parts[0], parts[1], branch

    @staticmethod
    def get_default_branch(owner: str, repo: str, token: Optional[str] = None) -> str:
        """获取仓库默认分支"""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        resp = requests.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=headers)
        resp.raise_for_status()
        return resp.json().get("default_branch", DEFAULT_BRANCH)

    @staticmethod
    @staticmethod
    def clone_or_pull(repo_url: str, clone_dir: Path, branch: str = DEFAULT_BRANCH, token: Optional[str] = None) -> str:
        """克隆或更新仓库，返回本地路径"""
        try:
            # 解析 owner 和 repo
            url_path = repo_url.replace("https://github.com/", "").replace("http://github.com/", "").replace("www.", "")
            url_path = url_path.rstrip(".git").split("/")
            owner, repo_name = url_path[0], url_path[1]

            # 使用 token 构建 URL
            if token and "github.com" in repo_url:
                url_with_token = repo_url.replace("https://github.com/", f"https://{token}@github.com/")
                url_with_token = url_with_token.replace("http://github.com/", f"https://{token}@github.com/")
            else:
                url_with_token = repo_url

            repo_clone_dir = clone_dir / f"{owner}_{repo_name}"

            if repo_clone_dir.exists():
                print(f"📂 仓库已存在，更新中...")
                repo = git.Repo(repo_clone_dir)
                origin = repo.remotes.origin
                origin.pull()
            else:
                print(f"📥 正在克隆仓库...")
                git.Git().clone(url_with_token, str(repo_clone_dir), depth=1, branch=branch)

            return str(repo_clone_dir)
        except git.GitCommandError as e:
            raise RuntimeError(f"克隆仓库失败: {e}")
        except Exception as e:
            raise RuntimeError(f"处理仓库失败: {e}")


class LocalProjectParser:
    """解析本地项目"""

    @staticmethod
    def parse(project_path: Path) -> ProjectInfo:
        """解析本地项目"""
        info = ProjectInfo()

        # 获取项目名称
        info.name = project_path.name

        # 查找 README
        for readme_name in ["README.md", "README.rst", "README.txt", "README"]:
            readme_path = project_path / readme_name
            if readme_path.exists():
                info.readme_content = readme_path.read_text(encoding="utf-8", errors="ignore")[:2000]
                break

        # 解析目录结构
        info.structure = LocalProjectParser._get_structure(project_path)

        # 解析依赖文件
        info = LocalProjectParser._parse_dependency_files(project_path, info)

        # 解析核心文件
        info = LocalProjectParser._parse_core_files(project_path, info)

        # 提取入口点
        info.entry_points = LocalProjectParser._find_entry_points(project_path)

        # 检测技术栈
        info.tech_stack = LocalProjectParser._detect_tech_stack(project_path)

        return info

    @staticmethod
    def _get_structure(path: Path, prefix: str = "", max_depth: int = 3, current_depth: int = 0) -> List[str]:
        """获取目录结构"""
        if current_depth >= max_depth:
            return []

        structure = []
        try:
            items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            for item in items:
                name = item.name

                # 跳过忽略的目录和文件
                if item.is_dir() and name in IGNORED_DIRS:
                    continue
                if item.is_file():
                    if name in IGNORED_FILES or any(name.endswith(ext.lstrip("*")) for ext in IGNORED_FILES):
                        continue

                indent = "  " * current_depth
                structure.append(f"{indent}{'📁 ' if item.is_dir() else '📄 '}{name}")

                if item.is_dir() and current_depth < max_depth - 1:
                    structure.extend(LocalProjectParser._get_structure(item, str(item), max_depth, current_depth + 1))
        except PermissionError:
            pass

        return structure

    @staticmethod
    def _parse_dependency_files(path: Path, info: ProjectInfo) -> ProjectInfo:
        """解析依赖文件"""
        # requirements.txt
        req_file = path / "requirements.txt"
        if req_file.exists():
            content = req_file.read_text(encoding="utf-8", errors="ignore")
            info.requirements = [line.strip() for line in content.splitlines()
                                if line.strip() and not line.startswith("#")]

        # setup.py
        setup_py = path / "setup.py"
        if setup_py.exists():
            info.setup_py = setup_py.read_text(encoding="utf-8", errors="ignore")[:2000]

        # pyproject.toml
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            info.pyproject_toml = pyproject.read_text(encoding="utf-8", errors="ignore")[:2000]

        # package.json
        package_json = path / "package.json"
        if package_json.exists():
            info.package_json = package_json.read_text(encoding="utf-8", errors="ignore")
            try:
                pkg_data = json.loads(info.package_json)
                info.description = pkg_data.get("description", "")
                info.dependencies = pkg_data.get("dependencies", {})
            except json.JSONDecodeError:
                pass

        # Cargo.toml
        cargo_toml = path / "Cargo.toml"
        if cargo_toml.exists():
            info.cargo_toml = cargo_toml.read_text(encoding="utf-8", errors="ignore")[:2000]

        # go.mod
        go_mod = path / "go.mod"
        if go_mod.exists():
            info.go_mod = go_mod.read_text(encoding="utf-8", errors="ignore")[:1000]

        return info

    @staticmethod
    def _parse_core_files(path: Path, info: ProjectInfo) -> ProjectInfo:
        """解析核心代码文件"""
        core_patterns = ["main.py", "app.py", "index.py", "server.py", "cli.py",
                        "main.rs", "lib.rs", "main.go", "main.dart",
                        "index.js", "app.js", "server.js", "index.ts",
                        "src/main/java", "src/App.js", "src/App.tsx",
                        "main.c", "main.cpp"]

        for pattern in core_patterns:
            file_path = path / pattern
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8", errors="ignore")[:3000]
                info.core_files[pattern] = content

        # 查找所有代码文件作为备选
        if not info.core_files:
            for ext in ["*.py", "*.js", "*.ts", "*.tsx", "*.go", "*.rs", "*.java"]:
                for code_file in path.rglob(ext):
                    if any(ignored in str(code_file) for ignored in IGNORED_DIRS):
                        continue
                    rel_path = code_file.relative_to(path)
                    if len(info.core_files) >= 5:
                        break
                    content = code_file.read_text(encoding="utf-8", errors="ignore")[:2000]
                    info.core_files[str(rel_path)] = content

        return info

    @staticmethod
    def _find_entry_points(path: Path) -> List[str]:
        """查找入口点"""
        entry_points = []
        entry_patterns = [
            "main.py", "app.py", "__main__.py", "run.py",
            "index.js", "server.js", "app.js",
            "main.go", "cmd/main.go"
        ]

        for pattern in entry_patterns:
            file_path = path / pattern
            if file_path.exists():
                entry_points.append(pattern)

        return entry_points

    @staticmethod
    def _detect_tech_stack(path: Path) -> List[str]:
        """检测技术栈"""
        stack = []

        # 按文件检测
        if list(path.rglob("*.py")):
            stack.append("Python")
        if list(path.rglob("*.js")):
            stack.append("JavaScript")
        if list(path.rglob("*.ts")) or list(path.rglob("*.tsx")):
            stack.append("TypeScript")
        if list(path.rglob("*.go")):
            stack.append("Go")
        if list(path.rglob("*.rs")):
            stack.append("Rust")
        if list(path.rglob("*.java")):
            stack.append("Java")
        if list(path.rglob("*.dart")):
            stack.append("Dart/Flutter")
        if list(path.rglob("*.rb")):
            stack.append("Ruby")
        if list(path.rglob("*.php")):
            stack.append("PHP")
        if list(path.rglob("*.cs")):
            stack.append("C#")
        if list(path.rglob("*.cpp")) or list(path.rglob("*.cc")):
            stack.append("C++")

        # 按配置文件检测
        if (path / "requirements.txt").exists():
            stack.append("pip")
        if (path / "package.json").exists():
            stack.append("npm/yarn")
        if (path / "Cargo.toml").exists():
            stack.append("Cargo")
        if (path / "go.mod").exists():
            stack.append("Go modules")
        if (path / "pom.xml").exists() or (path / "build.gradle").exists():
            stack.append("Maven/Gradle")
        if (path / "Dockerfile").exists():
            stack.append("Docker")
        if (path / ".github/workflows").exists():
            stack.append("GitHub Actions")

        return stack


class ReadmeGenerator:
    """README 生成器"""

    DEFAULT_TEMPLATE = """# {project_name}

{project_description}

[![License](https://img.shields.io/badge/license-{license}-blue.svg)](LICENSE)
{badges}

## 📖 目录

- [项目介绍](#项目介绍)
- [功能特点](#功能特点)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [安装部署](#安装部署)
- [使用示例](#使用示例)
- [项目结构](#项目结构)
- [配置说明](#配置说明)
- [常见问题](#常见问题)
- [贡献指南](#贡献指南)
- [更新日志](#更新日志)
- [许可证](#许可证)

---

## 项目介绍

{project_intro}

## 功能特点

{features}

## 技术栈

{tech_stack}

## 快速开始

### 前置要求

{requirements}

### 安装

{installation}

### 运行

{usage}

## 安装部署

{deployment}

## 使用示例

{examples}

## 项目结构

```text
{structure}
```

## 配置说明

{configuration}

## 常见问题

{faq}

## 贡献指南

{contributing}

## 更新日志

{changelog}

## 许可证

本项目基于 {license} 许可证开源，详见 [LICENSE](LICENSE) 文件。

---

*由 README Generator 自动生成 ✨*
"""

    def __init__(self, project_info: ProjectInfo, model: str = DEFAULT_MODEL):
        self.info = project_info
        self.model = model

    def generate(self, template: Optional[str] = None, custom_instructions: Optional[str] = None, provider: str = "anthropic") -> str:
        """生成 README"""
        # 如果有现有 README，先分析它
        existing_readme = ""
        if self.info.readme_content:
            print("📄 检测到现有 README，进行内容分析...")
            existing_readme = self.info.readme_content

        # 构建提示词
        prompt = self._build_prompt(existing_readme, custom_instructions)

        # 调用 API
        print(f"🤖 正在调用 {'MiniMax' if provider == 'minimax' else 'Anthropic'} AI 生成 README...")
        content = self._call_llm_api(prompt, provider)

        # 如果有模板，用模板格式化
        if template:
            content = self._apply_template(template, content)

        return content

    def _build_prompt(self, existing_readme: str = "", custom_instructions: Optional[str] = None) -> str:
        """构建提示词"""
        # 准备代码片段
        code_snippets = []
        for filename, content in list(self.info.core_files.items())[:5]:
            code_snippets.append(f"### {filename}\n```\n{content[:1500]}\n```")
        code_text = "\n\n".join(code_snippets)

        # 准备目录结构
        structure_text = "\n".join(self.info.structure[:50]) if self.info.structure else "未检测到"

        # 准备依赖
        deps_text = ", ".join(self.info.requirements[:20]) if self.info.requirements else "无"

        # 准备可选章节
        extra_readme_section = f"**现有 README (如有，请参考并保留有价值内容)**:\n{existing_readme[:2000]}" if existing_readme else ""
        extra_custom_section = f"**自定义要求**:\n{custom_instructions}" if custom_instructions else ""

        prompt = f"""## 任务
你是一位经验丰富的开源项目维护专家，擅长编写专业、清晰、吸引人的 README.md 文档。请根据以下项目信息，生成一个符合开源规范的专业 README.md。

## 项目信息

**项目名称**: {self.info.name}
**技术栈**: {', '.join(self.info.tech_stack) if self.info.tech_stack else '未知'}
**依赖**: {deps_text}

**入口文件**: {', '.join(self.info.entry_points) if self.info.entry_points else '未知'}

**目录结构**:
```text
{structure_text}
```

**核心代码片段**:
{code_text}

{extra_readme_section if extra_readme_section else ""}

{extra_custom_section if extra_custom_section else ""}

## 输出要求

1. **完整专业**：包含所有标准模块（项目介绍、功能特点、快速开始、安装部署、使用示例、项目结构、配置说明、FAQ、贡献指南、许可证）
2. **准确描述**：准确描述项目的功能、用途和使用方式，不要编造
3. **代码真实**：示例代码必须真实可运行，反映项目的实际用法
4. **格式规范**：使用 Markdown 格式，适当使用 emoji 增强可读性
5. **吸引眼球**：README 是项目的门面，要有吸引力

## 输出格式
直接输出完整的 README.md 内容，不要添加任何解释说明。"""

        return prompt

    def _call_llm_api(self, prompt: str, provider: str = "anthropic") -> str:
        """调用大模型 API"""
        if provider == "minimax":
            return self._call_minimax_api(prompt)
        else:
            return self._call_anthropic_api(prompt)

    def _call_anthropic_api(self, prompt: str) -> str:
        """调用 Anthropic API"""
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        if not api_key:
            raise ValueError("请设置环境变量 ANTHROPIC_API_KEY 或 CLAUDE_API_KEY")

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true"
        }

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        return result["content"][0]["text"]

    def _call_minimax_api(self, prompt: str) -> str:
        """调用 MiniMax API"""
        api_key = os.environ.get("MINI_MAX_API_KEY") or os.environ.get("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("请设置环境变量 MINI_MAX_API_KEY")

        # MiniMax 模型映射
        model_map = {
            "claude-sonnet-4-6": "MiniMax-Text-01",
            "claude-opus-4-6": "MiniMax-Text-01",
            "claude-haiku-4-5": "MiniMax-Text-01",
        }
        model = model_map.get(self.model, "MiniMax-Text-01")

        url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": model,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        # MiniMax 返回格式: {"choices": [{"message": {"content": "..."}}]}
        return result["choices"][0]["message"]["content"]

    def _apply_template(self, template: str, content: str) -> str:
        """应用模板"""
        # 简单模板替换
        replacements = {
            "{project_name}": self.info.name,
            "{project_description}": self.info.description or "暂无描述",
            "{license}": self.info.license or "MIT",
        }

        result = template
        for key, value in replacements.items():
            result = result.replace(key, value)

        return content


def main():
    parser = argparse.ArgumentParser(
        description="GitHub README 一键生成工具 - 输入本地项目或 GitHub 链接，自动生成专业 README.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s ./my_project
  %(prog)s ./my_project -o README.md
  %(prog)s https://github.com/owner/repo
  %(prog)s https://github.com/owner/repo --branch develop
  %(prog)s ./my_project -t ./my_template.md

环境变量:
  ANTHROPIC_API_KEY  - Anthropic API 密钥
  MINI_MAX_API_KEY   - MiniMax API 密钥 (使用 --provider minimax 时)
  GITHUB_TOKEN       - GitHub 访问令牌 (可选，用于私有仓库)
        """
    )

    parser.add_argument("source", help="本地项目路径或 GitHub 仓库链接")
    parser.add_argument("-o", "--output", help="输出文件路径 (默认: README.md)", default="README.md")
    parser.add_argument("-t", "--template", help="自定义模板文件路径")
    parser.add_argument("-b", "--branch", help="GitHub 仓库分支 (默认: main)", default=DEFAULT_BRANCH)
    parser.add_argument("--token", help="GitHub Token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--model", help=f"使用的模型 (默认: {DEFAULT_MODEL})", default=DEFAULT_MODEL)
    parser.add_argument("--provider", help="API 提供商: anthropic 或 minimax (默认: anthropic)", default="anthropic")
    parser.add_argument("--custom", help="自定义指令，给 AI 的额外要求")

    args = parser.parse_args()

    try:
        project_path = Path(args.source)
        info: ProjectInfo

        if str(args.source).startswith("http://") or str(args.source).startswith("https://"):
            # GitHub 仓库
            if "github.com" not in args.source:
                print("❌ 只支持 GitHub 仓库", file=sys.stderr)
                sys.exit(1)

            print(f"🌐 检测到 GitHub 仓库链接...")
            owner, repo, branch = GitHubRepoParser.parse_url(args.source)

            # 获取默认分支
            if args.branch == DEFAULT_BRANCH and "@" not in str(args.source):
                try:
                    default_branch = GitHubRepoParser.get_default_branch(owner, repo, args.token)
                    if default_branch != DEFAULT_BRANCH:
                        branch = default_branch
                except:
                    pass

            print(f"📦 仓库: {owner}/{repo} | 分支: {branch}")

            # 克隆仓库
            clone_dir = Path.home() / ".readme_generator_cache"
            clone_dir.mkdir(parents=True, exist_ok=True)
            local_path = GitHubRepoParser.clone_or_pull(args.source, clone_dir, branch, args.token)

            print(f"📂 本地路径: {local_path}")
            info = LocalProjectParser.parse(Path(local_path))
            info.repository_url = f"https://github.com/{owner}/{repo}"
        else:
            # 本地项目
            if not project_path.exists():
                print(f"❌ 路径不存在: {project_path}", file=sys.stderr)
                sys.exit(1)

            # 如果传入的是文件，使用其所在目录
            if project_path.is_file():
                print(f"📄 检测到文件，使用其所在目录: {project_path.parent}")
                project_path = project_path.parent

            print(f"📂 正在解析本地项目: {project_path}")
            info = LocalProjectParser.parse(project_path)

        # 打印解析结果
        print(f"\n📊 解析结果:")
        print(f"   项目名称: {info.name}")
        print(f"   技术栈: {', '.join(info.tech_stack) if info.tech_stack else '未知'}")
        print(f"   依赖数量: {len(info.requirements)}")
        print(f"   核心文件: {len(info.core_files)}")
        print(f"   入口点: {', '.join(info.entry_points) if info.entry_points else '未找到'}")

        # 生成 README
        template_content = None
        if args.template:
            template_path = Path(args.template)
            if template_path.exists():
                template_content = template_path.read_text(encoding="utf-8")
                print(f"📝 使用自定义模板: {args.template}")
            else:
                print(f"⚠️ 模板文件不存在: {args.template}")

        generator = ReadmeGenerator(info, args.model)
        readme_content = generator.generate(template_content, args.custom, args.provider)

        # 保存
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(readme_content)

        print(f"\n✅ README 生成成功: {output_path}")
        print(f"\n{'=' * 60}")
        print(readme_content[:2000] + "..." if len(readme_content) > 2000 else readme_content)
        print(f"{'=' * 60}")
        print(f"\n💡 提示：请检查并手动调整生成的 README，确保准确无误")

    except requests.exceptions.HTTPError as e:
        print(f"❌ API 请求失败: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
