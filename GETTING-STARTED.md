# Getting started

This guide takes a laptop with nothing installed to a lecture notebook running in the
browser. It assumes no previous experience of programming, of the terminal or of git.

Read [Before you start](#before-you-start). Then follow the part for your computer:
[Part A for macOS](#part-a-macos) or [Part B for Windows](#part-b-windows). After that,
both systems continue with [Part C](#part-c-working-in-the-environment).

Set aside an afternoon, and do it at home on a good connection. The downloads come to a
few gigabytes.

## Contents

- [Before you start](#before-you-start)
- [Part A: macOS](#part-a-macos)
- [Part B: Windows](#part-b-windows)
- [Part C: Working in the environment](#part-c-working-in-the-environment)
- [Part D: Submitting work](#part-d-submitting-work)
- [Part E: Keeping up to date, and when something goes wrong](#part-e-keeping-up-to-date-and-when-something-goes-wrong)

## Before you start

### What is installed

| Piece | What it is |
|---|---|
| **Terminal** | A window in which you type commands instead of clicking. On macOS the program is called Terminal. On Windows you will use the *Anaconda Prompt*. |
| **git** | A program that records the history of a folder of files and copies it between computers. |
| **GitHub** | The website that hosts the course material, at <https://github.com/claudio-ICL/unito26>. |
| **The repository** | The folder of course material: lecture notebooks, the `unito26` Python package, and its tests. Downloading a copy of it with git is called *cloning*. |
| **conda** | A program that installs Python and Python libraries. On macOS it comes from *Miniforge*, on Windows from *Anaconda*. |
| **An environment** | A self-contained folder, created by conda, holding one version of Python and one set of libraries. The course uses an environment called `unito26`, built from the file `unito26.yml` in the repository. |
| **Jupyter** | A program that runs in the browser and shows *notebooks*: documents that mix text, code, and the output of that code. The lectures are notebooks. |

These pieces work together as follows:
1. git brings the repository onto the laptop.
2. conda reads `unito26.yml` from the repository and builds the environment.
3. Jupyter, started from inside the environment, opens the notebooks of the repository.

### Four words

- **Command**: a line of text typed into the terminal and sent with Enter.
- **Prompt**: the text the terminal prints at the start of the line while it waits for a
  command. For example:
  - `yourname@MacBook-Air ~ %` on macOS;
  - `(base) C:\Users\yourname>` on Windows.

  A name in round brackets at the start is the active environment.
- **Current folder**: the terminal is always in one folder, and commands act there.
- **Path**: the address of a file or folder, such as `/Users/yourname/code/unito26` on
  macOS or `C:\Users\yourname\code\unito26` on Windows. The home folder has a shorthand:
  `~` on macOS and `%USERPROFILE%` on Windows.

### How to read this guide

A grey box holds commands. Type each line at the prompt exactly as written, or copy and
paste it, then press Enter. Wait for the prompt to come back before you type the next line.
Never type the prompt itself.

When a command prints an error, stop there and look it up in
[Part E](#part-e-keeping-up-to-date-and-when-something-goes-wrong). If Part E does not
cover it, copy the command, the full text of the error and the number of the step, and
bring them to the lab.

### What is needed

- About 8 GB of free disk space.
- A connection that can download a few gigabytes.
- On macOS, the password you log in with. The installation of git asks for it.

## Part A: macOS

### A1. Open Terminal

Press ⌘-Space, type `Terminal`, and press Enter. A window opens with a prompt ending in `%`.
To find it again easily, right-click its icon in the Dock and choose
*Options → Keep in Dock*.

Try two commands:

```
pwd
ls
```

`pwd` prints the current folder, which is your home folder, `/Users/yourname`. `ls` lists
what is in it: `Desktop`, `Documents`, `Downloads`, and so on.

```
cd Desktop
pwd
cd ..
```

`cd Desktop` moves into the folder `Desktop`, and `cd ..` moves back up one level.

### A2. Check for an existing conda

```
conda --version
```

- If this prints `command not found`, go on to A3.
- If it prints a version, such as `conda 24.11.3`, conda is already installed, usually
  through Anaconda. Do not install a second one. Update the one you have:

  ```
  conda update -n base conda
  ```

  Answer `y` when asked. If conda asks you to accept Anaconda's Terms of Service, answer
  `a`. Then do A3, skip A4, and continue from A5.

### A3. Install git

```
xcode-select --install
```

A dialog appears. Click **Install**, not *Get Xcode*: that is a separate download of more
than 10 GB that is not needed. Accept the licence and wait; it takes between 5 and 30
minutes. The prompt comes back at once: wait until the dialog says *The software was
installed*, and click **Done** before going on.

If the terminal prints a message that the command line tools are already installed, git is
already there.

Check that it worked:

```
git --version
```

This prints `git version 2.` followed by more numbers.

### A4. Install Miniforge

On Apple Silicon, first run `uname -m`. It must print `arm64`. If it prints `x86_64`,
Terminal is running under Rosetta: quit Terminal, go in Finder to *Applications →
Utilities*, select Terminal, press ⌘I, untick *Open using Rosetta*, and open Terminal
again.

This downloads the installer and runs it:

```
curl -fsSLo Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-$(uname -m).sh"
bash Miniforge3.sh
```

`$(uname -m)` inserts the type of processor: `arm64` on Apple Silicon (M1, M2 and later)
and `x86_64` on Intel. The same command therefore serves both kinds of Mac.

The installer goes through five steps:

1. *Please, press ENTER to continue*: press Enter. The licence appears. Press Space to
   scroll through it, or `q` to skip to the end.
2. *Do you accept the license terms? [yes|no]*: type `yes` in full and press Enter.
3. *Miniforge3 will now be installed into this location*: press Enter to accept
   `/Users/yourname/miniforge3`. The installation takes a minute or two.
4. *Do you wish to update your shell profile to automatically initialize conda?*: type
   `yes`. The default here is no.
5. The installer finishes with *Thank you for installing Miniforge3!*

Quit Terminal completely with ⌘Q, not just the window, and open it again. The prompt now
begins with `(base)`. Check:

```
conda --version
rm Miniforge3.sh
```

The second line deletes the installer, which is no longer needed.

If you answered no at step 4, run the following, then quit and reopen Terminal:

```
~/miniforge3/bin/conda init zsh
```

### A5. Tell git who you are

```
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global pull.ff only
```

Use your own name, and the email address you use (or will use) on GitHub. The third line
makes `git pull` stop with a plain message when it cannot simply update your copy.

### A6. Clone the repository

```
mkdir -p ~/code
cd ~/code
git clone https://github.com/claudio-ICL/unito26.git
cd unito26
```

- `mkdir -p ~/code` creates a folder called `code` in your home folder. It does nothing if
  the folder already exists.
- `git clone` downloads the repository into `~/code/unito26`.
- `cd unito26` moves into it.

`ls` now shows `README.md`, `notebooks`, `unito26.yml` and the rest.

This folder, `~/code/unito26`, is the **repository root**. Every command from here on is
run from inside it.

### A7. Create the environment

```
conda env create -f unito26.yml
```

conda reads `unito26.yml`, downloads Python and the libraries listed there, and installs
the course package from this folder. This takes 3 to 10 minutes.
- `Solving environment` can appear to stand still for a minute.
- The last stage is `Installing pip dependencies`.
- The command has finished when it prints

  ```
  # To activate this environment, use
  #
  #     $ conda activate unito26
  ```

  and the prompt comes back.

Then activate the environment:

```
conda activate unito26
```

The prompt now begins with `(unito26)` instead of `(base)`.

If the creation stopped with an error, or was interrupted, remove the half-built
environment and create it again, answering `y` when asked:

```
conda env remove -n unito26
conda env create -f unito26.yml
```

### A8. Download the data

The lectures use the free sample data of LOBSTER: one trading day on NASDAQ, 21 June 2012.

1. Open <https://php.lobsterdata.com/info/DataSamples.php> in the browser. No account is
   needed.
2. Next to **AMZN**, click the download link for **Level 10**. Do the same for **INTC**.
   This gives two files in `Downloads`:
   - `LOBSTER_SampleFile_AMZN_2012-06-21_10.zip`
   - `LOBSTER_SampleFile_INTC_2012-06-21_10.zip`

   Safari unzips them itself, into folders with the same names. With another browser,
   double-click each zip in Finder.
3. Create the data folder and open it in Finder:

   ```
   mkdir -p data/lobster
   open data/lobster
   ```

4. From the two unzipped folders, drag the four `.csv` files into the Finder window of
   `lobster`. Drag the files themselves, not the folders they came in. The
   `LOBSTER_SampleFiles_ReadMe.txt` file can stay where it is.
5. Check:

   ```
   ls data/lobster
   ```

   This must list exactly these four files:

   ```
   AMZN_2012-06-21_34200000_57600000_message_10.csv
   AMZN_2012-06-21_34200000_57600000_orderbook_10.csv
   INTC_2012-06-21_34200000_57600000_message_10.csv
   INTC_2012-06-21_34200000_57600000_orderbook_10.csv
   ```

Together they take about 260 MB. Do not double-click them: Numbers opens large files
slowly, and a file saved back from Numbers is no longer one the notebooks can read.

### A9. Check the installation

With `(unito26)` at the start of the prompt:

```
python --version
python -m pytest tests/
```

- The first command prints `Python 3.12` or a later version.
- The second runs the tests of the course package. It ends with a line such as
  `==== … passed, … skipped in …s ====`. Both *passed* and *skipped* are fine.
  Only *failed* or *error* means a problem.

Now go to [Part C](#part-c-working-in-the-environment).

### A10. Every later session

Open Terminal and run:

```
cd ~/code/unito26
conda activate unito26
git pull
jupyter notebook
```

`git pull` fetches the lectures published since your last session. If it refuses, see
[Part E](#git-pull-refuses).

## Part B: Windows

### B1. Two settings first

**System type.** Open *Settings → System → About* and read *System type*.
- *64-bit operating system, x64-based processor* is the usual case.
- *ARM-based processor* (Snapdragon laptops, some Surface models): the steps below still
  work on Windows 11, where the x64 installers run under emulation, only more slowly.

**File name extensions.** Make Explorer show the extension at the end of every file name:
- Windows 11: *View → Show → File name extensions*.
- Windows 10: the *View* tab, then tick *File name extensions*.

Without this, a file called `hello.py.txt` is shown as `hello.py`.

### B2. Check for an existing Anaconda

If you have Miniconda or Miniforge, keep it. Wherever this guide says *Anaconda Prompt*,
use *Anaconda Prompt (miniconda3)* or *Miniforge Prompt*.

Open the Start menu and type `Anaconda Prompt`, then `Miniforge Prompt`.
- If neither is found, go on to B3.
- If one is found, open it and run:

  ```
  conda --version
  ```

  If this prints a version, conda is already installed. Update it in that window:

  ```
  conda update -n base conda
  ```

  Answer `y` when asked. If conda asks you to accept Anaconda's Terms of Service, answer
  `a`. Then do B3, skip B4, and continue from B5.

### B3. Install git

1. Download the installer from <https://git-scm.com/downloads/win>. Choose the 64-bit
   *Git for Windows Setup*.
2. Run it. Keep the default on every screen except the editor screen:
   - *Choosing the default editor used by Git*: choose **Use Notepad as Git's default
     editor**. The default, Vim, is hard to leave for anyone who has not used it.
   - *Adjusting your PATH environment*: keep **Git from the command line and also from
     3rd-party software**.
   - *Choose a credential helper*: keep **Git Credential Manager**.

### B4. Install Anaconda

1. Go to <https://www.anaconda.com/download>. The page asks for an email address; the
   link *Skip registration* below the form goes straight to the downloads. Download the
   Windows 64-bit installer.
2. Run it:
   - *Select Installation Type*: **Just Me**.
   - *Choose Install Location*: keep `C:\Users\yourname\anaconda3`. If your user name
     contains a space or an accented letter (`C:\Users\Mario Rossi`, `C:\Users\Nicolò`),
     type `C:\anaconda3` instead, because some packages fail under such paths.
   - *Advanced Installation Options*: leave *Add Anaconda3 to my PATH environment
     variable* unticked, and keep the other options as they are.
   - The installation takes several minutes.
3. On the last screen, untick any offer to launch Anaconda Navigator or the tutorials.
   Navigator is not used in this course.

If conda asks you to accept Anaconda's Terms of Service at any point, answer `a`.

### B5. Open the Anaconda Prompt

Open the Start menu, type `Anaconda Prompt`, and open it. To find it again easily,
right-click *Anaconda Prompt* in the Start menu and choose *Pin to Start*. **Every Windows
command in this guide is typed into this window.**

The prompt looks like `(base) C:\Users\yourname>`.
- If the line starts with `PS` instead, the window is PowerShell. Close it and open the
  *Anaconda Prompt*.
- The *Anaconda PowerShell Prompt* is a different program. Do not use it: some commands in
  this guide do not work there.

Try a few commands:

```
cd
dir
cd Desktop
cd ..
```

`cd` on its own prints the current folder, and `dir` lists what is in it. `cd Desktop`
moves into the folder `Desktop`, and `cd ..` moves back up one level. Windows separates
folders with a backslash, `\`.

To paste a command into the window, right-click or press Ctrl-V.

Check that git can be found:

```
git --version
```

This prints `git version 2.` followed by more numbers.
- If it says `'git' is not recognized`, close the window and open a new Anaconda Prompt.
  A window opened before git was installed does not see it.
- If a new window still does not find git, run the git installer again and check the
  PATH screen (B3).

### B6. Tell git who you are

```
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global pull.ff only
```

Use your own name, and the email address you use (or will use) on GitHub. The third line
makes `git pull` stop with a plain message when it cannot simply update your copy.

### B7. Clone the repository

The course folder must not be synchronised by OneDrive. Folders synchronised by OneDrive
show a cloud icon or a green tick in Explorer. The `code` folder created below normally is
not. If it shows the icon, use `C:\code` in its place.

```
mkdir "%USERPROFILE%\code"
cd "%USERPROFILE%\code"
git clone https://github.com/claudio-ICL/unito26.git
cd unito26
```

- `mkdir` creates a folder called `code` in your home folder. If it says the folder
  already exists, carry on.
- `git clone` downloads the repository into it.
- `cd unito26` moves into the repository.

`dir` now shows `README.md`, `notebooks`, `unito26.yml` and the rest.

Keep the quotation marks around paths. They are needed when the user name contains a space.

This folder, `%USERPROFILE%\code\unito26`, is the **repository root**. Every command from
here on is run from inside it.

### B8. Create the environment

```
conda env create -f unito26.yml
```

conda reads `unito26.yml`, downloads Python and the libraries listed there, and installs
the course package from this folder. On Windows this often takes 10 to 20 minutes, because
the antivirus inspects every file as it is written. Do not close the window.
- `Solving environment` can appear to stand still for a minute.
- The last stage is `Installing pip dependencies`.
- The command has finished when it prints

  ```
  # To activate this environment, use
  #
  #     $ conda activate unito26
  ```

  and the prompt comes back.

Then activate the environment:

```
conda activate unito26
```

The prompt now begins with `(unito26)` instead of `(base)`.

If the creation stopped with an error, or was interrupted, remove the half-built
environment and create it again, answering `y` when asked:

```
conda env remove -n unito26
conda env create -f unito26.yml
```

### B9. Download the data

The lectures use the free sample data of LOBSTER: one trading day on NASDAQ, 21 June 2012.

1. Open <https://php.lobsterdata.com/info/DataSamples.php> in the browser. No account is
   needed.
2. Next to **AMZN**, click the download link for **Level 10**. Do the same for **INTC**.
   This gives two files in `Downloads`:
   - `LOBSTER_SampleFile_AMZN_2012-06-21_10.zip`
   - `LOBSTER_SampleFile_INTC_2012-06-21_10.zip`
3. In Explorer, right-click each zip, choose *Extract All…*, then *Extract*. Each opens as
   a folder of the same name.
4. Create the data folder and open it in Explorer:

   ```
   mkdir data\lobster
   explorer data\lobster
   ```

5. From the two extracted folders, drag the four `.csv` files into the Explorer window of
   `lobster`. Drag the files themselves, not the folders they came in. The
   `LOBSTER_SampleFiles_ReadMe.txt` file can stay where it is.
6. Check:

   ```
   dir data\lobster
   ```

   This must list exactly these four files:

   ```
   AMZN_2012-06-21_34200000_57600000_message_10.csv
   AMZN_2012-06-21_34200000_57600000_orderbook_10.csv
   INTC_2012-06-21_34200000_57600000_message_10.csv
   INTC_2012-06-21_34200000_57600000_orderbook_10.csv
   ```

Together they take about 260 MB. Do not double-click them: Excel opens large files slowly,
and a file saved back from Excel is no longer one the notebooks can read.

### B10. Check the installation

With `(unito26)` at the start of the prompt:

```
where python
python --version
python -m pytest tests/
```

- `where python` lists every Python on the laptop, and the first line is the one that
  runs. That first line must end in `\envs\unito26\python.exe`. Lines after it, such as
  one ending in `\WindowsApps\python.exe`, are normal.
- `python --version` prints `Python 3.12` or a later version.
- The last command runs the tests of the course package. It ends with a line such as
  `==== … passed, … skipped in …s ====`. Both *passed* and *skipped* are fine. Only
  *failed* or *error* means a problem.

Now go to [Part C](#part-c-working-in-the-environment).

### B11. Every later session

Open the Anaconda Prompt and run:

```
cd "%USERPROFILE%\code\unito26"
conda activate unito26
git pull
jupyter notebook
```

`git pull` fetches the lectures published since your last session. If it refuses, see
[Part E](#git-pull-refuses).

## Part C: Working in the environment

From here on, the steps are the same on both systems. Where a command differs, it is given
twice: first for macOS, then for Windows.

### C1. What activation does

```
conda env list
```

This lists the environments. The active one is marked with `*`:

```
base                     /Users/yourname/miniforge3
unito26              *   /Users/yourname/miniforge3/envs/unito26
```

- `conda activate unito26` makes `unito26` the active environment, and
  `conda deactivate` goes back to `base`.
- Activation lasts only as long as the terminal window. A new window starts in `base`,
  so run `conda activate unito26` again.
- Course code always runs in `unito26`. `base` does not have the course libraries.

### C2. Python, interactively

With `unito26` active:

```
python
```

The prompt changes to `>>>`. This is Python waiting for code, no longer the terminal. Type
these lines one at a time, pressing Enter after each:

```python
1 + 1
import numpy as np
np.sqrt(2)
import unito26
unito26.__file__
exit()
```

`unito26.__file__` prints where the course package is. It is inside your clone: conda
installed the package from the repository folder itself, so it always runs the version you
have on disk. `exit()` returns to the terminal.

### C3. Starting Jupyter

From the repository root, with `unito26` active:

```
jupyter notebook
```

The terminal prints a few lines, and the browser opens on a page listing the folders of the
repository. That page is the Jupyter *file browser*.

The terminal window is now running Jupyter.
- Leave it open. You may minimise it, but closing it stops Jupyter.
- If the browser does not open, look in the terminal for a line starting with
  `http://localhost:8888/tree?token=`. Copy the whole line into the browser's address bar.
- To stop Jupyter, choose *File → Shut Down* in the browser. Alternatively, press Ctrl-C
  in the terminal, then type `y` and press Enter.

Start Jupyter only this way: from a terminal where `unito26` is active. Do not open it by
double-clicking a notebook file, from Anaconda Navigator, or from an editor such as VS Code.
The lectures draw their figures with the library plotly, and the figures appear only when
Jupyter itself was started from the `unito26` environment. Started any other way, every
cell runs without an error and the figures stay blank.

### C4. A script

A script is a text file of Python code whose name ends in `.py`. It is run from the
terminal.

1. In the file browser, click *New* (top right), then *New Folder*. A folder called
   *Untitled Folder* appears. Tick the box next to it, click *Rename*, and name it
   `scratch`. The folder `scratch` is ignored by git: what you put there stays on your
   laptop and never goes into the repository.
2. Open `scratch`. Click *New → New File*. An empty file opens in an editor. Choose
   *File → Rename…* and name it `hello.py`.
3. Type:

   ```python
   import numpy as np

   prices = np.array([100.0, 101.5, 99.8, 102.3])
   returns = np.diff(np.log(prices))
   print("log returns:", returns)
   print("mean:", returns.mean())
   ```

   Save with ⌘S on macOS or Ctrl-S on Windows.
4. The first terminal window is busy running Jupyter, so open a second one: ⌘N in
   Terminal, or a new Anaconda Prompt. Run the script from the repository root:

   macOS:

   ```
   cd ~/code/unito26
   conda activate unito26
   python scratch/hello.py
   ```

   Windows:

   ```
   cd "%USERPROFILE%\code\unito26"
   conda activate unito26
   python scratch\hello.py
   ```

   It prints the three log returns and their mean.

### C5. A notebook

1. In the file browser, inside `scratch`, click *New*, then *Python 3 (ipykernel)* under
   *Notebook*. A new tab opens with an empty notebook. Choose *File → Rename…* and name it
   `first.ipynb`.
2. Click the first cell, type the following, and press Shift-Enter:

   ```python
   import sys
   sys.executable
   ```

   The output is the path of the Python running the notebook. It must contain
   `envs/unito26`. On Windows it shows as `envs\\unito26`, because the output doubles
   every backslash.
3. In the next cell, type the following and press Shift-Enter:

   ```python
   import plotly.express as px
   px.line(x=[0, 1, 2, 3], y=[0, 1, 4, 9])
   ```

   A small figure appears. If the space stays blank, Jupyter was not started as described
   in C3.

### C6. Notebook basics

- **Cells.** A notebook is a sequence of cells. A *code* cell holds Python. A *Markdown*
  cell holds text. The type of the selected cell is shown in the toolbar, and can be
  changed there.
- **Running a cell.** Shift-Enter runs the selected cell and moves to the next one.
- **The mark to the left of a code cell.**
  - `[ ]`: the cell has not been run.
  - `[*]`: the cell is running.
  - `[3]`: the cell has finished, and it was the third cell to run.
- **Order.** A cell sees what the cells run before it defined. What counts is the order in
  which the cells were *run*, not their order on the page. *Kernel → Restart Kernel and
  Run All Cells…* runs the whole notebook afresh, from top to bottom.
- **The kernel.** The kernel is the Python behind the notebook.
  - *Kernel → Interrupt Kernel* stops a cell that takes too long.
  - *Kernel → Restart Kernel…* clears every variable.
- **Saving.** Jupyter saves on its own every couple of minutes, and on ⌘S or Ctrl-S.
- **Closing.** Closing the browser tab leaves the kernel running. *File → Close and Shut
  Down Notebook* stops it as well.

### C7. Running lecture 01

1. In the file browser, open `notebooks`, then `lectures`, then
   `01-the-limit-order-book.ipynb`.
2. If a *Select Kernel* dialog appears, choose **Python 3 (ipykernel)**. That is the Python
   of the `unito26` environment. Do not choose any other entry the list may offer.
3. Choose *Kernel → Restart Kernel and Run All Cells…* and confirm.
4. Wait until no cell shows `[*]`, then scroll through. The cell that loads the data prints
   one line per stock, of the form

   ```
   AMZN: … states, from …s to …s after midnight
   INTC: … states, from …s to …s after midnight
   ```

   and the figures below it appear.

If the cell prints `absent, so every figure below is skipped: AMZN, INTC` instead, the
notebook cannot find the data. Go back to A8 or B9.

### C8. Keeping your own version of a lecture

Running a lecture changes its file: Jupyter saves the outputs into it. Because of this,
`git pull` will refuse to update that lecture later (see [Part E](#git-pull-refuses)).

To keep a version with your own notes:
1. Choose *File → Save Notebook As…*.
2. The dialog shows the path `notebooks/lectures/…`. Replace only the file name at its
   end, keeping the folder, for example `notebooks/lectures/01-my-notes.ipynb`. Use no
   spaces.

A lecture finds its data through a path that starts from its own folder,
`../../data/lobster`, so a copy saved in another folder cannot find the data.

### C9. Installing further libraries

With `unito26` active:

```
conda install -c conda-forge name-of-library
```

Always install into `unito26`, never into `base`. A library installed this way may be removed
by the update described in Part E, *When `unito26.yml` has changed*.

## Part D: Submitting work

This part is needed only to submit an assignment, which is done as a *pull request*: a
proposal of changes to the repository, reviewed on GitHub.

1. **A GitHub account.** Create one at <https://github.com>, if you do not have one.
   Once the lecturer has invited you to the repository as a collaborator, GitHub sends an
   email. Accept the invitation from that email, or at
   <https://github.com/claudio-ICL/unito26/invitations>.
2. **The GitHub command-line tool.** Download it from <https://cli.github.com>. On macOS,
   take the file ending in `.pkg`; on Windows, the one ending in `.msi`. Run the
   installer, then open a new terminal window.
3. **Log in**, from the repository root:

   ```
   gh auth login
   ```

   Answer its questions as follows:
   - *Where do you use GitHub?*: **GitHub.com**.
   - *Preferred protocol*: **HTTPS**.
   - *Authenticate Git with your GitHub credentials?*: **Yes**.
   - *How would you like to authenticate?*: **Login with a web browser**.

   It shows a one-time code. Press Enter, and a browser opens. Type the code there and
   authorise.
4. **The notebook hook**, set once from the repository root:

   ```
   git config core.hooksPath .githooks
   ```

   The hook removes the outputs from notebooks as they are committed.
   - It uses the program `nbstripout` from the `unito26` environment. Therefore commit from
     the terminal with `unito26` active. A commit from VS Code or GitHub Desktop stops with
     `nbstripout not found`.
   - Give notebooks names without spaces.
5. **The cycle.** Follow [`CONTRIBUTING.md`](CONTRIBUTING.md) from *The development
   cycle* onwards. Its *One-time setup* is covered by this guide. In particular, do not
   run its `git clone git@…` line: it needs SSH keys, and your clone already exists.

## Part E: Keeping up to date, and when something goes wrong

### git pull refuses

The message reads:

```
error: Your local changes to the following files would be overwritten by merge:
        notebooks/lectures/01-the-limit-order-book.ipynb
Please commit your changes or stash them before you merge.
Aborting
```

Running a notebook writes its outputs into the file, so git sees a change it will not
overwrite. Save anything you want to keep under a new name (C8). Then discard the changes
to the lectures and pull again:

```
git restore notebooks/lectures
git pull
```

`git restore` puts back every lecture as your last pull left it, and your changes to them
are lost. Copies saved under other names are not affected.

### git pull says it is not possible to fast-forward

`fatal: Not possible to fast-forward, aborting.` means a commit was made on `main` in your
copy. Bring the message to the lab.

### conda or python is not recognised

- **macOS, `zsh: command not found: conda`.** Either Terminal was not quit and reopened
  after A4, or you answered no at its step 4. The fix is in A4.
- **Windows, `'conda' is not recognized as an internal or external command`.** The window
  is not the Anaconda Prompt (B5).
- **Windows, typing `python` opens the Microsoft Store.** The window is not the Anaconda
  Prompt, or `unito26` is not active. Run `conda activate unito26` in the Anaconda Prompt.

### No module named 'unito26'

The error `ModuleNotFoundError: No module named 'unito26'` (or `'numpy'`, `'plotly'`, and
so on) means the code is not running in the `unito26` environment.
- **In the terminal.** The prompt does not begin with `(unito26)`. Run
  `conda activate unito26`.
- **In a notebook.** Jupyter was started without `unito26` active. Stop it, activate the
  environment, and start it again (C3).
- **If the environment is active and the error persists,** the repository folder was
  probably moved or renamed after the environment was created. From the repository's new
  location, with `unito26` active, run:

  ```
  pip install -e .
  ```

### The figures are blank

Jupyter was not started from the `unito26` environment: for example, it was opened from
Navigator, from an editor, or with `base` active. Stop every running Jupyter, then start it
as described in C3.

### A lecture says the data is absent

Lecture 01 prints `absent, so every figure below is skipped: AMZN, INTC`, and lecture 02
prints `no sample file under` followed by the folder where it looked.

From the repository root, `ls data/lobster` (macOS) or `dir data\lobster` (Windows) must
list the four files of A8 or B9 directly. The usual causes are:
- the files are still inside the unzipped folder, as in
  `data/lobster/LOBSTER_SampleFile_AMZN_2012-06-21_10/`;
- the browser changed a name on download, for example by adding ` (1)`;
- the folder `data` was created somewhere other than the repository root.

### When `unito26.yml` has changed

When the course adds a library, the environment has to be brought up to date. From the
repository root, run:

```
conda env update -f unito26.yml --prune
```

`--prune` also removes libraries you installed yourself (C9). Install them again afterwards.

### Starting the environment again

If the environment is broken beyond the cases above, remove it and create it afresh,
answering `y` when asked:

```
conda deactivate
conda env remove -n unito26
conda env create -f unito26.yml
```

This deletes none of the course files: the repository and the data stay where they are.

### Anything else

Copy the command, the full text of the error and the number of the step you were on, and
bring them to the lab.
