# Privex's Network Looking Glass

Our **network looking glass** is a small Python 3 web application written using the Flask framework, offering basic `mtr` and `ping` functionality from a smooth web UI.

For safety, the hostname/IP is validated upon entry to ensure no arbitrary commands can be passed in, as well as an ACL blacklist which by default blocks local IPv4 / IPv6 subnets such as `10.0.0.0/8` `192.168.0.0/16` and `fe80::/10` (see `core.py` for the default blocked subnets, and how to add your own blacklist).

You can test it out using our production looking glass website: [Privex AS210083 Network Looking Glass](https://lg.privex.io)

![Screenshot of Looking Glass](https://i.imgur.com/V0wDWcK.png)

# License

This project is licensed under the **GNU AGPL v3**

For full details, please see `LICENSE.txt` and `AGPL-3.0.txt`.

Here's the important parts:

 - If you use this software (or substantial parts of it) to run a public service (including any separate user interfaces 
   which use it's API), **you must display a link to this software's source code wherever it is used**.
   
   Example: **This website uses the open source [Privex Looking Glass](https://github.com/Privex/looking-glass)
   created by [Privex Inc.](https://www.privex.io)**
   
 - If you modify this software (or substantial portions of it) and make it available to the public in some 
   form (whether it's just the source code, running it as a public service, or part of one) 
    - The modified software (or portion) must remain under the GNU AGPL v3, i.e. same rules apply, public services must
      display a link back to the modified source code.
    - You must attribute us as the original authors, with a link back to the original source code
    - You must keep our copyright notice intact in the LICENSE.txt file

 - Some people interpret the GNU AGPL v3 "linking" rules to mean that you must release any application that interacts
   with our project under the GNU AGPL v3.
   
   To clarify our stance on those rules: 
   
   - If you have a completely separate application which simply sends API requests to a copy of Privex Looking Glass
     that you run, you do not have to release your application under the GNU AGPL v3. 
   - However, you ARE required to place a notice on your application, informing your users that your application
     uses Privex Looking Glass, with a clear link to the source code (see our example at the top)
   - If your application's source code **is inside of Privex Looking Glass**, i.e. you've added your own Python
     views, templates etc. to a copy of this project, then your application is considered a modification of this
     software, and thus you DO have to release your source code under the GNU AGPL v3.

 - There is no warranty. We're not responsible if you, or others incur any damages from using this software.
 
 - If you can't / don't want to comply with these license requirements, or are unsure about how it may affect
   your particular usage of the software, please [contact us](https://www.privex.io/contact/). 
   We may offer alternative licensing for parts of, or all of this software at our discretion.

# Requirements

The looking glass is composed of two pieces:

 - The Trace / Ping tool (sometimes directly referred to as the "looking glass")
 - The BGP Peer / Prefix tracking tool

You can disable either part of the application using `.env` settings.

To run either of them, you need at the least:

 - **Ubuntu Bionic Server 18.04** is recommended, however other distros may work
 - **Python 3.7+** is strongly recommended (3.6 is the bare minimum)
 - **Redis** - Used for caching data, plus storing user's trace/ping requests and their results
 - **Yarn** and **NodeJS** for compiling the Vue JS components
 - Minimal hardware requirements, will probably run on as little as 512mb RAM and 1 core

For the trace / ping tool (the main "looking glass" part):

 - The utilities **mtr** and **iputils-ping**
 - **RabbitMQ Server** - Used for processing mtr/ping's in the background

For the BGP Peer / Prefix tool:

 - **PostgreSQL** (database server) - for storing the prefix data
 - An instance of [GoBGP](https://github.com/osrg/gobgp) connected to a BGP router
 

# Installation

Quickstart (Tested on Ubuntu Bionic 18.04 - may work on other Debian-based distros):

```
sudo apt update -y

####
# Core requirements:
#  - Python 3.7 is strongly recommended, we cannot guarantee compatibility with older versions
#  - Redis is used for caching, storing metadata about a request, and it's results upon completion
#  - Yarn is required for building the Vue JS frontend files
####
sudo apt install -y git python3.7 python3.7-venv python3.7-dev libpq-dev redis-server

# Install Yarn
curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | sudo apt-key add -
echo "deb https://dl.yarnpkg.com/debian/ stable main" | sudo tee /etc/apt/sources.list.d/yarn.list

sudo apt update -y && sudo apt install -y yarn

####
# To run the Trace / Ping part of the application, you need:
# 
#  - RabbitMQ is used for queueing and processing mtr/ping requests
#  - MTR is used for traceroutes, and iputils-ping is required as it offers a single `ping` command 
#    which works with both IPv4 and IPv6 
####
sudo apt install -y rabbitmq-server mtr-tiny iputils-ping

# For MTR to work correctly as non-privileged users, mtr-packet must be owned by root
# and set with the SUID bit (+s)
sudo chown root:root /usr/bin/mtr-packet
sudo chmod +s /usr/bin/mtr-packet 

####
# To run the BGP Peers and Prefixes part of the application, you need:
#
#  - PostgreSQL for storing the prefix data
#  - GoBGP for obtaining the BGP prefix data from (can either run locally, or on another server
####

sudo apt install -y postgresql

# To avoid timezone issues, set your PostgreSQL timezone to UTC
#
# Add this line to the file:
#
# timezone = 'UTC'
#
sudo vim /etc/postgresql/10/main/conf.d/timezone.conf
sudo systemctl enable postgresql
sudo systemctl restart postgresql

# Create a postgres user and database for the app
sudo su - postgres

# (as the user 'postgres')
# Create the Postgres user 'lg' (save the password somewhere safe, you'll need to put it in PSQL_PASS in .env)
createuser -SDRl -P lg
# Create the Postgres database 'lookingglass' owned by user 'lg'
createdb -O lg lookingglass
exit


# Install GoBGP (see example configuration in this README after you're done)
cd /tmp
wget https://github.com/osrg/gobgp/releases/download/v2.7.0/gobgp_2.7.0_linux_amd64.tar.gz
tar xzf gobgp_2.7.0_linux_amd64.tar.gz
sudo install -v gobgp gobgpd /usr/bin/

# Create user 'lg' to run the application under

adduser --gecos "" --disabled-login lg
sudo su - lg

###
# as user `lg`
###

# Clone the project
git clone https://github.com/Privex/looking-glass.git
cd looking-glass

pip3 install pipenv

# Create, activate and install python dependencies into a virtualenv with Python 3.7
# PIPENV_DONT_LOAD_ENV=1 stops pipenv from caching the .env file, so you can change settings
# without having to quit & restart the shell
pipenv install
PIPENV_DONT_LOAD_ENV=1 pipenv shell

cp .env.example .env
# edit .env with your favourite editor, adjust as needed
vim .env

# Migrate the database

flask db upgrade

# Install NodeJS using NVM, then build the JS

curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.34.0/install.sh | bash

export NVM_DIR="${XDG_CONFIG_HOME/:-$HOME/.}nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" # This loads nvm

nvm install --lts  # Install latest NodeJS LTS
yarn install       # Install project JS requirements
yarn build         # Build frontend JS files


###
# BELOW INSTRUCTIONS FOR DEVELOPMENT ONLY
###

# run flask dev server
flask run

# in another terminal session, e.g. with tmux/screen
# run the queue loader, which processes incoming mtr/ping's from rabbitmq
./manage.py queue

# to run GoBGP locally (edit gbgp.conf as required)
cp gbgp.example.conf gbgp.conf
sudo gobgpd -f gbgp.conf

# to load prefixes immediately from GoBGP
./run.sh cron

###
# RUNNING IN PRODUCTION
###

# exit out of the lg user and become your normal account / root
exit

# install the systemd services
cd /home/lg/looking-glass
sudo cp *.service /etc/systemd/system/
# install GoBGP configuration into /etc for the service to use it
sudo cp gbgp.example.conf /etc/gbgp.conf

# adjust the user/paths in the service files as needed
sudo vim /etc/systemd/system/lg-queue.service
sudo vim /etc/systemd/system/looking-glass.service

# once the service files are adjusted to your needs, enable and start them
sudo systemctl daemon-reload
sudo systemctl enable lg-queue.service looking-glass.service gobgp.service
sudo systemctl start looking-glass.service lg-queue.service gobgp.service

# set up a cron to load prefixes from GoBGP regularly

crontab -e
# m    h  dom mon dow   command
# */5  *   *   *   *    /home/lg/looking-glass/run.sh cron

# looking glass should now be running on 127.0.0.1:8282
# set up a reverse proxy such as nginx / apache pointed to the above host
# and it should be ready to go :)

```

# Updating your Looking Glass installation

For convenience, we have an `update` command in our `run.sh` which runs the various update steps for you, helping
avoid human error such as forgetting to re-run `yarn install` to update NodeJS packages, or `pipenv install` to update
python packages.

```
./run.sh update
```

The `update` command does the following:

 - Runs `git pull` to update your files using our Github repo
 - Runs `pipenv update` to ensure any new Python package dependencies are installed, and updates existing packages
 - Runs `yarn install` to update any NodeJS dependencies, and `yarn build` to re-build the frontend VueJS components
 - Runs `flask db upgrade` to make sure any new PostgreSQL migrations are applied
 - Displays post update information, so you remember to update your systemd service files (if required), and
   restart the systemd services.
 

# Using GoBGP

An example configuration is included as `gbgp.example.conf` - you'll need to customise this with your server's
external IPv4 / IPv6 addresses and point it at your router.

For most cases, it's fine to leave the local ASN as the private ASN `65000`

Make sure to change the following settings:
 
 - `local-address-list` - Your public (or LAN) IPv4 and/or IPv6 address that your router will be pointed towards
 - `peer-as` - (one for v4 and one for v6) The ASN of the router you're obtaining the prefixes from
 - `neighbor-address` -  (one for v4 and one for v6) Your router's IPv4 / v6 address
 - `local-address` - (under neighbors.transport.config) This should generally match the IPv6 address in your local address list

Here's an example BGP configuration for Cisco IOS (commands may differ between models and OS versions), using
the example IP's in `gbgp.example.conf`:

```
ip bgp-community new-format
ipv6 multicast rpf use-bgp

router bgp 210083
    no bgp enforce-first-as
    bgp log-neighbor-changes
    !
    template peer-policy GOBGP
        next-hop-unchanged allpaths
        send-community both
        send-label
    exit-peer-policy
    !
    neighbor 192.168.56.56 remote-as 65000
    neighbor 192.168.56.56 ebgp-multihop 255
    neighbor 2001:abcd:def1::123 remote-as 65000
    neighbor 2001:abcd:def1::123 ebgp-multihop 255
    !
    address-family ipv4
        neighbor 192.168.56.56 activate
        neighbor 192.168.56.56 inherit peer-policy GOBGP
        neighbor 192.168.56.56 route-server-client
    exit-address-family
    !
    address-family ipv6
        neighbor 2001:abcd:def1::123 activate
        neighbor 2001:abcd:def1::123 inherit peer-policy GOBGP
        neighbor 2001:abcd:def1::123 route-server-client
        neighbor 2001:abcd:def1::123 next-hop-unchanged
    exit-address-family
    !
exit

```

Again, this is just an example configuration. You should adjust it for your own requirements, or if you aren't running
a Cisco IOS router, then simply use it as a guideline.

For best compatibility, we use `ebgp-multihop` in the above configuration and in the gbgp.example.conf, this
allows for your GoBGP server to be running on a non-adjacent network, which may be common in datacenters with 
various layers of routers.

To ensure that the **next hop** and **source asn** data isn't mangled by the router, it's recommended to enable the
**route server client** option on your router for the GoBGP neighbour (see example config above). This ensures that 
prefixes are sent to GoBGP exactly as they came into the router, without replacing the **next hop** or adding it's 
own **source asn** to the path.

**Running GoBGP**

GoBGP must be ran as root, as BGP uses TCP port 179 (on Linux, ports below 1024 are privileged, only root can listen
on them).

Copy the example config, adjust it as required, and then run it like so:

```
# to run GoBGP locally (edit gbgp.conf as required)
cp gbgp.example.conf gbgp.conf
sudo gobgpd -f gbgp.conf
```

# Configuration

Common configuration options are included in `.env.example` and are generally self explanatory.

For the BGP Peers and Prefixes part of the application, the following settings are useful for
controlling pagination of prefix data:

DEFAULT_API_LIMIT = limit results from the api/v1/prefixes API to this many prefixes when
the limit parameter is not explicitly provided (the UI uses this default value)

MAX_API_LIMIT = maximum value that the limit parameter of the api/v1/prefixes API can be
explicitly set to

For information about other configuration options, check the comments in the following files:

 - `lg/base.py` - Shared settings between both apps
 - `lg/lookingglass/settings.py` - Settings specific to the Trace / Ping tool
 - `lg/peerapp/settings.py` - Settings specific to the BGP Peers tool 


# Contributing

We're very happy to accept pull requests, and work on any issues reported to us. 

Here's some important information:

**Reporting Issues:**

 - For bug reports, you should include the following information:
     - Version of the project you're using - `git log -n1`
     - The Python package versions you have installed - `pip3 freeze`
     - Your python3 version - `python3 -V`
     - Your operating system and OS version (e.g. Ubuntu 18.04, Debian 7)
 - For feature requests / changes
     - Clearly explain the feature/change that you would like to be added
     - Explain why the feature/change would be useful to us, or other users of the tool
     - Be aware that features/changes that are complicated to add, or we simply find un-necessary for our use of the tool 
       may not be added (but we may accept PRs)
    
**Pull Requests:**

 - We'll happily accept PRs that only add code comments or README changes
 - Use 4 spaces, not tabs when contributing to the code
 - You can use features from Python 3.4+ (we run Python 3.7+ for our projects)
    - Features that require a Python version that has not yet been released for the latest stable release
      of Ubuntu Server LTS (at this time, Ubuntu 18.04 Bionic) will not be accepted. 
 - Clearly explain the purpose of your pull request in the title and description
     - What changes have you made?
     - Why have you made these changes?
 - Please make sure that code contributions are appropriately commented - we won't accept changes that involve 
   uncommented, highly terse one-liners.

**Legal Disclaimer for Contributions**

Nobody wants to read a long document filled with legal text, so we've summed up the important parts here.

If you contribute content that you've created/own to projects that are created/owned by Privex, such as code or 
documentation, then you might automatically grant us unrestricted usage of your content, regardless of the open source 
license that applies to our project.

If you don't want to grant us unlimited usage of your content, you should make sure to place your content
in a separate file, making sure that the license of your content is clearly displayed at the start of the file 
(e.g. code comments), or inside of it's containing folder (e.g. a file named LICENSE). 

You should let us know in your pull request or issue that you've included files which are licensed
separately, so that we can make sure there's no license conflicts that might stop us being able
to accept your contribution.

If you'd rather read the whole legal text, it should be included as `privex_contribution_agreement.txt`.

# Thanks for reading!

**If this project has helped you, consider [grabbing a VPS or Dedicated Server from Privex](https://www.privex.io) - prices start at as little as US$8/mo (we take cryptocurrency!)**
