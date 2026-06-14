# clenv — CLI Environment Manager

> **Your CLI junk drawer, finally cleaned up.**

`clenv` is a terminal tool that scans your system for forgotten CLI tools installed via **brew, npm, pip, pipx, cargo, gem, go, apt** and more — then lets you cleanly remove them (binaries *and* leftover config files) through a slick interactive TUI.

And yes, when you're done, it offers to **uninstall itself** too.

---

## 🤔 Why clenv?

As developers, our terminal is our second home. Over time, we install dozens of CLI tools and utilities to solve immediate problems—a quick formatter here, an API client there, an experimental utility somewhere else. 

While it is easy to clean up desktop applications (they sit visibly in our Applications folder or Start Menu, prompting us to uninstall them when they are no longer needed), **CLI tools are invisible**. They hide away in global `npm`, `pip`, `cargo`, `gem`, or `brew` paths, quietly consuming disk space and cluttering our shell environment long after we have forgotten they even exist.

`clenv` was built to solve this exact problem:
*   **Find the Forgotten:** It aggregates and scans your package managers and system directories to surface every globally-installed CLI tool in one unified view.
*   **Track Utility:** It analyzes your shell history to show you which commands you *actually* use versus which ones have been sitting idle for months.
*   **Clean the Leftovers:** It removes not just the binary, but the configurations, cache files, and hidden directories (`~/.config/tool`, `~/.cache/tool`) that standard package managers leave behind.

---


## ✨ Features

| Feature | Details |
|---|---|
| 🔍 **Cross-manager scan** | brew · npm -g · pip · pipx · cargo · gem · go · apt/dpkg |
| 🕒 **Last-used detection** | Checks shell history to show which tools you actually use |
| 🗑 **Config cleanup** | Removes `~/.config/tool`, `~/.cache/tool`, dotfiles |
| ☑️ **Interactive TUI** | Multi-select with keyboard navigation |
| 🪄 **Self-uninstall** | Removes itself on exit — zero hypocrisy |
| 🐍 **Single language** | Pure Python, no compilation needed |

---

## 🚀 Install (one command)

```bash
curl -fsSL https://raw.githubusercontent.com/AnasNafees1802/clenv/main/install.sh | bash
```

Then just run:

```bash
clenv
```

### Alternative installs

```bash
# via pipx (recommended — keeps it isolated)
pipx install git+https://github.com/AnasNafees1802/clenv.git

# via pip
pip install git+https://github.com/AnasNafees1802/clenv.git

# run without installing (one-liner)
pipx run --spec git+https://github.com/AnasNafees1802/clenv.git clenv
```

---

## 🖥 Usage

```
clenv
```

That's it. The TUI guides you through everything:

1. **Scan** — detects all CLI tools across package managers
2. **Review** — see tool name, source, version, and whether you've used it recently
3. **Select** — checkbox-select the tools you want to remove
4. **Remove** — clenv runs the right uninstall command per tool and cleans up configs
5. **Exit** — clenv offers to remove itself, then says goodbye

---

## 📦 What gets scanned

| Manager | How detected |
|---|---|
| **Homebrew** | `brew list --formula` |
| **npm** | `npm list -g --depth=0` |
| **pipx** | `pipx list --json` |
| **pip** | `pip list --format=json` + binary check |
| **Cargo** | `~/.cargo/bin/` + `.crates2.json` |
| **RubyGems** | `gem list` + binary check |
| **Go** | `$GOPATH/bin/` |
| **APT/dpkg** | `dpkg -l` + binary check |

---

## 🔒 Safety

- **Nothing is deleted without confirmation.** You review a list and explicitly confirm before anything is removed.
- **Dry-run friendly.** The table view shows you everything without making any changes.
- **Config removal is optional.** You're asked separately whether to remove leftover config/cache files.
- **Self-uninstall is always opt-in.** clenv asks at the end; you can always say no.

---

## 🛠 Requirements

- Python **3.9+**
- Works on **macOS** and **Linux**
- Windows support via WSL

---

## 🤝 Contributing

PRs welcome! Areas to improve:
- Windows native support (choco, winget, scoop)
- `--dry-run` / `--json` output flags
- Fish/Nushell history parsing
- `dnf`/`yum` scanner for RHEL-based systems

---

## 👤 Author

**Anas Nafees**  
🔗 [LinkedIn Profile](https://www.linkedin.com/in/anas-nafees/)

---

## 📄 License

MIT — see [LICENSE](LICENSE)

