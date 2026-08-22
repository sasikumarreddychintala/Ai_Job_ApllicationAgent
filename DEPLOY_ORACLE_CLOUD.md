# 🚀 Deploying to Oracle Cloud Always Free (Step-by-Step Guide)

This guide walks you through deploying your **AI Job Application Agent** on an **Oracle Cloud Always Free VM (4 Core ARM, 24 GB RAM, 200 GB Storage)** for **$0.00 forever**.

---

## 📋 Step 1: Create Oracle Cloud Always Free VM
1. Go to [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) and sign up.
2. In Oracle Cloud Console, navigate to **Compute ➡️ Instances ➡️ Create Instance**.
3. Configure the VM:
   * **Image:** `Ubuntu 24.04 LTS` (or `Ubuntu 22.04 LTS`)
   * **Shape:** `Ampere VM.Standard.A1.Flex` (Choose **4 OCPUs, 24 GB RAM** — 100% Free Tier eligible).
   * **Networking:** Ensure **Assign a public IPv4 address** is checked.
   * **SSH Keys:** Save the private key (`ssh-key.key`) to your computer.
4. Click **Create** and note the **Public IP Address** (e.g. `129.153.xx.xx`).

---

## 🔓 Step 2: Open Port 8000 in Security List & Firewall
1. In Oracle Console: **Networking ➡️ Virtual Cloud Networks ➡️ Your VCN ➡️ Security Lists ➡️ Default Security List**.
2. Click **Add Ingress Rules**:
   * **Source CIDR:** `0.0.0.0/0`
   * **IP Protocol:** `TCP`
   * **Destination Port Range:** `8000`
   * Click **Add Ingress Rules**.

---

## 💻 Step 3: Connect to Your VM & Install Docker
Connect to your VM from your terminal (PowerShell, Command Prompt, or Mac/Linux terminal):
```bash
ssh -i /path/to/ssh-key.key ubuntu@<YOUR_VM_PUBLIC_IP>
```

Install Docker & Docker Compose:
```bash
# Update and install Docker
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git

# Add ubuntu user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Open Ubuntu internal firewall for port 8000
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

---

## 🚀 Step 4: Clone & Run the Agent
```bash
# 1. Clone your repository
git clone https://github.com/<your-username>/Job_Application_Agent.git
cd Job_Application_Agent

# 2. Create your .env file
cp .env.example .env
nano .env  # Add your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID

# 3. Start the entire system in the background with Docker Compose
docker compose up -d --build
```

---

## 🤖 Step 5: Pull Lightweight AI Model in Ollama
```bash
# Pull the 3B model inside the Ollama container (takes ~30 seconds)
docker exec -it agent-ollama ollama pull qwen2.5:3b-instruct
```

---

## 🎉 Done! Your System is Live 24/7 for $0:
* **Web UI Dashboard:** `http://<YOUR_VM_PUBLIC_IP>:8000`
* **Telegram Alerts & Bot:** Actively running and responding to `/fresher`, `/junior`, `/top`, and sending tailored PDF resumes directly to your phone 24/7!
* **Auto-Restart:** If the cloud server ever reboots, Docker automatically brings your agent and database back online seamlessly (`restart: unless-stopped`).
