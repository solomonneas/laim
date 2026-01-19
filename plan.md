\# 🛠️ Final Project Plan: Categorized Lab Inventory Server (LAIM)



\*\*Objective:\*\* Deploy a modern, high-density hardware inventory server as a repeatable standalone service within a Proxmox VE 9.1.2 environment.



\### 🏗️ Environment \& Deployment

\- \*\*Host OS:\*\* Proxmox VE 9.1.2 (Base: Debian 13.2 "Trixie").

\- \*\*Kernel:\*\* Linux 6.17 stable default.

\- \*\*Deployment Method:\*\* Unprivileged LXC container with Docker Nesting enabled (`features: nesting=1`).

\- \*\*Orchestration:\*\* Docker Compose running inside the Debian 13 LXC.



\### 📊 Application Requirements

\- \*\*Hardware Categories:\*\* Laptops, Desktops, Smart TVs, Servers, and WAPs.

\- \*\*Data Model:\*\*

&nbsp;   - \*\*Fields:\*\* Hostname, Room Location (2266, 2265), Serial Number, MAC Address, Inventory Asset Tag, Item Type (Enum), and Sub-location (e.g., Rack 1, Shelf B).

\- \*\*Search \& UI:\*\*

&nbsp;   - Real-time search engine filtering the table as the user types.

&nbsp;   - Category-specific filter buttons (e.g., "Show only WAPs").

\- \*\*Auth:\*\* RBAC logic with 1 Master Superuser and 3 Admin accounts created via an automated seed script.



\### 🎨 Design \& Typography (2026 Modern Tech Look)

\- \*\*Primary Header Font:\*\* 'Geist Sans' (Mechanical/Swiss precision).

\- \*\*Body/Table Font:\*\* 'Inter' (Optimized for digital data legibility).

\- \*\*Technical/Strings Font:\*\* 'Geist Mono' (For MACs, Serials, and Hostnames).

\- \*\*UX Requirement:\*\* Implementation of CSS `font-variant-numeric: tabular-nums;` to ensure inventory numbers and serials align vertically for rapid scanning.



\### 📂 Required File Deliverables

1\. `proxmox\_lxc\_create.sh`: Host-side script to automate CT creation on Proxmox 9.1.2, set Debian 13 template, and enable nesting.

2\. `docker-compose.yml`: Orchestrating the FastAPI web app and PostgreSQL database.

3\. `app/models.py`: SQLAlchemy models using an Enum for the 5 categories.

4\. `app/main.py`: FastAPI backend with CRUD and specialized search/filter endpoints.

5\. `app/seed.py`: Python script to create the initial admin users.

6\. `templates/dashboard.html`: Jinja2 template with Tailwind CSS, Geist/Inter fonts, and Tabular Numbers logic.

7\. `setup.sh`: Container-side script to install dependencies, build images, and seed the database.



\### 💡 Philosophy

The UI should be beautiful, but fast and responsive. It will not be holding a big data base, think a couple hundred items MAX. everything should be organized, fast, and repeatable. I expect a fully functional, professional-grade inventory tool upon execution.

