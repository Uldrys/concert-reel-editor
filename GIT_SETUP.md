# Git setup — how to push this to GitHub

This file walks you through committing this skill to a new GitHub repo. Once
done, you can delete this file (it's not part of the skill itself).

## 1. Move the folder where you want it

Currently the folder lives at `C:\Users\simsi\Videos\SIBB\concert-reel-editor`
because my Cowork session went into a weird state with the WSL mount and I
couldn't request access to `Documents` or your `dev` folder directly.

From a Windows terminal:

```cmd
move "C:\Users\simsi\Videos\SIBB\concert-reel-editor" "C:\Users\simsi\Documents\concert-reel-editor"
```

Or from WSL:

```bash
mv "/mnt/c/Users/simsi/Videos/SIBB/concert-reel-editor" "/home/simon/dev/concert-reel-editor"
```

Pick wherever fits your workflow.

## 2. Initialize the git repo

```bash
cd path/to/concert-reel-editor
git init -b main
git add .
git status   # sanity check — confirm depot/ and sortie/ are NOT staged
git commit -m "Initial commit: concert-reel-editor skill"
```

## 3. Create the GitHub repo

On github.com:
- New repository, name: `concert-reel-editor` (or whatever you prefer)
- Public, no README/license/gitignore (we have those already)
- Don't initialize with any files
- Create

## 4. Push

```bash
git remote add origin git@github.com:<your-username>/concert-reel-editor.git
git push -u origin main
```

(or `https://github.com/...` if you use HTTPS auth)

## 5. Sanity check on GitHub

Once pushed, verify on the repo page:
- `SKILL.md`, `README.md`, `LICENSE`, `.gitignore` at the root
- `scripts/` has 7 Python files
- `references/` has 4 markdown files
- `examples/` has 3 example files
- `depot/` and `sortie/` exist but are empty (just `.gitkeep`)

## 6. (Optional) Test it locally

Add it as a Cowork/Claude Code skill and try invoking it on a new video. If
something doesn't behave right, edit the SKILL.md or scripts, commit, push.

## 7. Cleanup leftover

If there's a stray `concert-reel-editor-readme-test.txt` in your SIBB folder
from my earlier write tests, just delete it — it's not part of the skill.

---

That's it. After step 4 the repo is live on GitHub and you can share the URL
with anyone who wants to install the skill.
