# React 学习大纲

这是一个使用 [Quarto](https://quarto.org/) 构建的 React 学习路线网站，适合已经具备 HTML 和 JavaScript 基础的初学者。

## 本地预览

安装 Quarto 后，在项目目录执行：

```bash
quarto preview
```

## 构建网站

```bash
quarto render
```

生成的网站文件位于 `_site` 目录。

## 内容结构

课程文章按“章节 → 小节”组织在 `chapters` 目录中：

```text
chapters/
├── 02-foundations/
│   ├── 01-html-css.qmd
│   ├── 02-javascript-basics.qmd
│   └── 03-basic-exercises.qmd
└── 03-react-basics/
    ├── 01-introduction/
    │   ├── index.qmd
    │   ├── 01-what-is-react.qmd
    │   └── ...
    ├── 02-jsx-components/
    │   └── index.qmd
    ├── 03-state-forms/
    │   └── index.qmd
    ├── 04-effects-data/
    │   └── index.qmd
    ├── 05-styling-design/
    │   └── index.qmd
    ├── 06-routing/
    │   └── index.qmd
    ├── 07-state-performance/
    │   └── index.qmd
    └── 08-engineering-testing/
        └── index.qmd
```

- 章节目录使用两位章节号和英文名称，例如 `03-react-basics`
- 文章文件使用两位小节号和英文名称，例如 `01-what-is-react.qmd`
- 小节包含多篇文章时，使用同名目录和 `index.qmd` 作为概览页
- 中文标题设置在文章 front matter 和 `_quarto.yml` 侧边栏中
- 新增或移动文章后，需要同步更新 `_quarto.yml` 和相关 `.qmd` 链接

## GitHub Pages

推送到 `main` 分支后，GitHub Actions 会自动构建网站并发布到 `gh-pages` 分支：

<https://codeideaai.github.io/react/>
