# Publishing Mimi World and opening it on the tablets

This is the phase 0 guide. It takes about 30 minutes, in five parts:

1. Create the repository on GitHub (in your web browser).
2. Make the first commit on your PC (PowerShell).
3. Send it to GitHub (PowerShell).
4. Switch on GitHub Pages (in your web browser).
5. Open the test page on both tablets, and send Claude a photo of the results.

Your GitHub user name is `barneyfin`, so the repository is `https://github.com/barneyfin/mimi-world` and the website will be `https://barneyfin.github.io/mimi-world/`.

---

## Part 1: Create the repository on GitHub

1. Go to https://github.com and sign in.
2. Click the **+** at the top right, then **New repository**.
3. Fill in the form:
   - **Repository name:** `mimi-world`
   - **Description:** leave it blank.
   - **Public:** selected. GitHub Pages needs a public repository on the free plan.
   - **Add a README file:** leave it OFF.
   - **Add .gitignore:** None.
   - **Choose a license:** None.

   These three must stay empty, because your folder already has its own files. If GitHub adds files as well, the two copies clash at Part 3.
4. Click **Create repository**.
5. GitHub shows a "Quick setup" page. Leave it open: you need the address it shows, which looks like `https://github.com/barneyfin/mimi-world.git`.

---

## Part 2: Make the first commit (PowerShell)

Open **Windows PowerShell**: Start menu, type `PowerShell`, and press Enter.

Type each command on its own, press Enter, and check the result before moving on.

**Command 1.** Go into the Mimi World folder:

```powershell
cd "C:\Users\barne\Documents\Calude Code\Mimi World"
```

- **Expect:** no output. The prompt changes to `PS C:\Users\barne\Documents\Calude Code\Mimi World>`.
- **If it says "Cannot find path":** check the spelling, including "Calude".

**Command 2.** Make the folder a git repository:

```powershell
git init -b main
```

- **Expect:** `Initialized empty Git repository in C:/Users/barne/Documents/Calude Code/Mimi World/.git/`
- **If it says `unknown switch 'b'`:** your git is older. Run `git init` instead; then, after command 6, run `git branch -M main`.

**Command 3.** Move the commit message into the hidden .git folder. This must come before command 4, so the message file isn't added to the repository:

```powershell
Move-Item CM1.txt .git\CM1.txt
```

- **Expect:** no output.

**Command 4.** Add every file:

```powershell
git add .
```

- **Expect:** no output.

**Command 5.** Check what's going in:

```powershell
git status --short
```

- **Expect:** these 9 lines, each starting with `A`:

  ```
  A  .gitattributes
  A  .gitignore
  A  README.md
  A  SETUP-HOSTING.md
  A  docs/icon-192.png
  A  docs/icon-512.png
  A  docs/index.html
  A  docs/manifest.json
  A  docs/sw.js
  ```

- **If `CM1.txt` is in the list:** command 3 didn't work. Run `git rm --cached CM1.txt`, then repeat commands 3 and 4.

**Command 6.** Make the commit:

```powershell
git commit -F .git\CM1.txt
```

- **Expect:** a first line like `[main (root-commit) 1a2b3c4] Phase 0: tablet test page for Mimi World`, then `9 files changed`.
- **If it says "Please tell me who you are":** git doesn't know your name on this computer. Run these two commands, one at a time, then run command 6 again:

  ```powershell
  git config --global user.name "Barney Finlayson"
  ```

  ```powershell
  git config --global user.email "you@example.com"
  ```

  Use the email address on your GitHub account.

---

## Part 3: Send it to GitHub (PowerShell)

**Command 7.** Tell git where the GitHub copy lives. Use the address from Part 1, step 5:

```powershell
git remote add origin https://github.com/barneyfin/mimi-world.git
```

- **Expect:** no output.
- **If it says "remote origin already exists":** run `git remote set-url origin https://github.com/barneyfin/mimi-world.git` instead.

**Command 8.** Send the commit:

```powershell
git push -u origin main
```

- **The first time:** a window opens asking you to sign in to GitHub. Choose **Sign in with your browser** and approve it in the browser. You won't be asked again on this PC.
- **Expect** the output to end with:

  ```
  * [new branch]      main -> main
  branch 'main' set up to track 'origin/main'.
  ```

- **If it says `src refspec main does not match any`:** the commit in command 6 didn't happen. Go back to command 6.
- **If it says `rejected` and `fetch first`:** GitHub added files in Part 1. Stop and tell Claude; don't force it.
- **If it says `GH007` or "private email":** your GitHub settings hide your email. Tell Claude and paste the message.

Refresh the GitHub page: your files should now be listed.

---

## Part 4: Switch on GitHub Pages (web browser)

1. On the `mimi-world` repository page, click **Settings** (the tab with the cog, top right of the repository).
2. In the left-hand list, under **Code and automation**, click **Pages**.
3. Under **Build and deployment**:
   - **Source:** Deploy from a branch
   - **Branch:** `main`, and in the second box choose `/docs`
   - Click **Save**.
4. Wait 1 to 3 minutes, then refresh the page. A box at the top says **Your site is live at** `https://barneyfin.github.io/mimi-world/`.
5. Open that address on your PC. You should see the night sky, a moon-coloured circle and three lilac Mimi on an asteroid. Try dragging one with the mouse.

This address is the one Mimi World keeps for good, so it only needs approving on the Fire once.

---

## Part 5: The tablets

Do both tablets. On each, follow the six steps in the page's **Results** panel (top right), then photograph the panel and send the photo to Claude.

### Doogee T30 Pro (Chrome)

1. Open **Chrome** and type the address: `barneyfin.github.io/mimi-world`
2. Follow the steps in the Results panel.
3. To add it to the home screen: tap Chrome's **⋮** menu, then **Add to home screen** (it may say **Install app**), then **Install** or **Add**.
4. Close Chrome, open Mimi World from its new home-screen icon, and try dragging again.
5. Turn Wi-Fi off, open it from the icon again, and open the Results panel.

### Fire HD 8 Kids (Amazon Kids profile)

First, on your PC or phone:

1. Open the Amazon Parent Dashboard at https://parents.amazon.co.uk and sign in.
2. Choose your child's profile, then its **settings**.
3. Find the web browser settings, called **Fire Tablet Web Browser** in Amazon's guides. Make sure the web browser is switched on.
4. Add `https://barneyfin.github.io/mimi-world/` to the list of approved websites.

Amazon changes these menus from time to time, so the names may differ slightly. Finding out what the Kids profile allows is part of this test: write down what you find, including anything it won't let you do.

Then on the Fire, in your child's profile:

5. Open the web browser (or the **Web** tab) and go to Mimi World.
6. Follow the steps in the Results panel. The Kids browser may not offer full screen or "add to home screen". That's fine: just note it.
7. Turn Wi-Fi off, open Mimi World again, and open the Results panel.

### What to send Claude

- A photo of the Results panel from each tablet, taken after step 5 of the panel's list.
- Anything that felt wrong: the Mimi lagging behind your finger, a sound that didn't play, a menu you couldn't find.

---

## Good to know

- **The website is public.** Anyone with the address can open it, though nobody will find it by chance. It holds nothing personal, and nothing in Mimi World will ever say your child's name.
- **Updates.** When Claude changes the game, you commit and push as above (with a new CMn.txt). GitHub Pages updates in a minute or two. Each tablet saves the new version in the background when it next opens the game, then switches to it at the start screen.
