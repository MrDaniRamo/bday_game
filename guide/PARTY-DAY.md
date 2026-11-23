# Running the party on your laptop (no coding needed)

These steps run the whole game from your Windows laptop. A free Cloudflare link puts it on the internet, so:

- **Phones can be on any connection**: mobile data or any Wi-Fi. Nobody has to join your Wi-Fi.
- **Nobody types a link**: captains scan a QR code on the TV.
- **You can test it this week**: friends can join from their own homes while your laptop runs it.

There are two parts:

- **Part A** happens **once**, about 15 minutes, any day before the party.
- **Part B** happens **every time** you play, including test runs, and takes about 1 minute.

---

## Part A: one-time setup

### A1. Get the game onto the laptop

**If you already have the `bday_game` folder from git**, open PowerShell in it and run `git pull origin main`. Then skip to A2.

**If you don't**, download it as a ZIP file:

1. Go to **https://github.com/MrDaniRamo/bday_game**.
2. Click the green **Code** button, then **Download ZIP**.
3. Open your **Downloads** folder, right-click `bday_game-main.zip`, and choose **Extract All… → Extract**.
4. Move the extracted folder somewhere easy to find, such as your **Desktop**.

The folder should contain `setup.bat` and `start-party.bat`.

### A2. Install everything

1. Open the folder and double-click **`setup.bat`**.
   - If Windows shows **"Windows protected your PC"**, click **More info**, then **Run anyway**.
2. A black window opens. The first time, it reports that some programs are missing (**Python**, **Node.js**, **cloudflared**) and offers to install them.
   - Type **Y** and press **Enter**.
   - If Windows asks "Do you want to allow this app to make changes?", click **Yes** each time.
3. When it says **"close this window and double-click setup.bat once more"**, do exactly that.
4. The second run installs the game's own parts, which takes a few minutes. Wait for **DONE** in green, then press **Enter**.

✅ **Checkpoint:** the window said **DONE**.

**If the automatic install doesn't work**, install the three programs yourself, then run `setup.bat` again:

| Program | Where to get it | Notes |
|---|---|---|
| Python | https://www.python.org/downloads/ | Tick **"Add python.exe to PATH"** at the start of the installer. |
| Node.js | https://nodejs.org/ | Use the **LTS** version and click Next through everything. |
| cloudflared | Search "cloudflared download", open the Cloudflare page, and get the **Windows 64-bit .msi** | Click Next through everything. |

---

## Part B: every time you play

### B1. Start the game

1. Plug the laptop in and connect it to the internet.
2. Double-click **`start-party.bat`**.
3. It asks you to **choose tonight's host password**. Type something only you know, then press **Enter**.
   - Don't use "party". The game's code is public, so anyone could guess that one.
4. If you played before, it asks whether to start fresh:
   - For a test run or the real party, type **NEW** and press **Enter**. This deletes the old teams, scores and bingo ticks.
   - To carry on where you stopped, for example after an accidental close, just press **Enter**.
5. If Windows asks whether to allow Python on networks, click **Allow**.
6. Wait about 15 seconds. Two things open in your browser:
   - **The links page**, with a QR code for each link (TV, host, captains, secret bingo).
   - **The TV page.**

✅ **Checkpoint:** the black window says **THE GAME IS RUNNING** and shows a link ending in `trycloudflare.com`.

> **Keep the black window open the whole time**, and keep the laptop **awake and plugged in**. Closing the window, or the laptop going to sleep, stops the game.
> To stop the laptop sleeping: **Settings → System → Power** → set "When plugged in, put my device to sleep after" to **Never**.

### B2. Set up the screens

| Who | What they do |
|---|---|
| **The TV** | Put the TV page on the TV, either with the laptop connected by HDMI or by opening the TV link on a smart TV's browser. Click **"Click to enable sound"** once. In the lobby it shows a big **"Captains: scan to join"** QR code. |
| **You (host)** | On the links page, scan the **Host** QR code with your phone and log in with tonight's password. |
| **The 5 captains** | They scan the QR code on the TV, then pick a team name and color. |
| **The 5 bingo players** | Send them the **Secret bingo** link **privately**, for example in a direct WhatsApp message. Never show it on the TV. They can start ticking right away, even before the teams exist. |

**The link changes every time you run `start-party.bat`.** Old links stop working, so share fresh ones each time. On the party day, start it once and leave it running.

### B3. During the party

Everything is on your host page:

- **Start game** once all 5 teams have joined. The TV QR code then disappears.
- **Open buzzers**, then use the **+/−** buttons to give points.
- **Images and sounds**: **Show** puts a picture on the TV, and **Clear the screen** takes it away.
- **At the end**: **Close ticking**, then **Apply bingo bonus**, then **Reveal the secret bingo**.

### B4. Stop the game

Click the black window and press **Enter**. The scores are saved, so if you need to restart, choose to continue the saved game.

---

## Testing this week

1. Do Part B with a friend or two. They can be at home: send them the captain or bingo link from the links page.
2. Try each of these:
   - A phone on **mobile data**
   - **Locking a phone** and unlocking it again
   - **Refreshing** a captain's page; they should get their team back
   - **Showing a picture**
   - **Applying the bingo bonus**
3. Stop the game, and next time choose **NEW** to start clean.

---

## If something goes wrong

| What you see | What to do |
|---|---|
| "Windows protected your PC" | Click **More info**, then **Run anyway**. |
| "The game is not set up yet" | Run `setup.bat` first (Part A). |
| "The game server did not start" | Close everything and try again. If it still fails, open the `logs` folder and send me `server.log`. |
| "Could not open the public link" | The laptop may be offline. Check the internet and run `start-party.bat` again. Or use the **Wi-Fi backup** shown in the window: phones join the laptop's Wi-Fi and open that address. |
| The link stopped working during the party | The laptop probably slept, lost internet, or the black window was closed. Run `start-party.bat` again, press **Enter** to **continue the saved game**, and share the new links. Everyone's team and score come back. |
| Captains say the page says "Connecting…" | Ask them to refresh. If it continues, check the black window is still open. |
| No sound on the TV | Click **"Click to enable sound"** on the TV page. |
| I forgot the host password | Stop the game (Enter in the black window), start it again, choose a new password, and choose to **continue the saved game**. |

**What hasn't been tested:** these scripts were written for Windows and checked carefully, but I couldn't run them on a Windows laptop. The game itself was tested in a browser at the same single address the scripts use. The Cloudflare link couldn't be opened from my test machine. **So do a full test run this week.**
