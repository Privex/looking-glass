# Privex's Network Looking Glass

Our **network looking glass** is a small Python 3 web application written using the Flask framework, offering basic `mtr` and `ping` functionality from a smooth web UI.

For safety, the hostname/IP is validated upon entry to ensure no arbitrary commands can be passed in, as well as an ACL blacklist which by default blocks local IPv4 / IPv6 subnets such as `10.0.0.0/8` `192.168.0.0/16` and `fe80::/10` (see `core.py` for the default blocked subnets, and how to add your own blacklist).

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

 - **Ubuntu Bionic Server 18.04** is recommended, however other distros may work
 - **RabbitMQ Server** - Used for processing mtr/ping's in the background
 - **Redis** - Used for temporarily storing user's requests and their results
 - **Python 3.7+** is strongly recommended (3.6 is the bare minimum)
 - The utilities **mtr** and **iputils-ping**
 - Minimal hardware requirements, will probably run on as little as 512mb RAM and 1 core

# Installation

Quickstart (Tested on Ubuntu Bionic 18.04 - may work on other Debian-based distros):

```
sudo apt update -y

####
#
#  - Python 3.7 is strongly recommended, we cannot guarantee compatibility with older versions
#  - RabbitMQ is used for queueing and processing mtr/ping requests
#  - Redis is used for storing metadata about a request, and it's results upon completion
#  - MTR is used for traceroutes, and iputils-ping is required as it offers a single `ping` command 
#    which works with both IPv4 and IPv6 
####
sudo apt install -y git python3.7 python3.7-venv rabbitmq-server redis-server mtr-tiny iputils-ping

# For MTR to work correctly as non-privileged users, mtr-packet must be owned by root
# and set with the SUID bit (+s)
sudo chown root:root /usr/bin/mtr-packet
sudo chmod +s /usr/bin/mtr-packet 

adduser --gecos "" --disabled-login lg
sudo su - lg

###
# as user `lg`
###

# Clone the project
git clone https://github.com/Privex/looking-glass.git
cd looking-glass

# Create and activate a virtualenv with Python 3.7
python3.7 -m venv venv
source venv/bin/activate
# Install the python packages required
pip3 install -r requirements.txt

cp .env.example .env
# edit .env with your favourite editor, adjust as needed
vim .env


###
# BELOW INSTRUCTIONS FOR DEVELOPMENT ONLY
###

# run flask dev server
flask run

# in another terminal session, e.g. with tmux/screen
# run the queue loader, which processes incoming mtr/ping's from rabbitmq
./manage.py queue

###
# RUNNING IN PRODUCTION
###

# exit out of the lg user and become your normal account / root
exit

# install the systemd services
cd /home/lg/looking-glass
sudo cp *.service /etc/systemd/system/

# adjust the user/paths in the service files as needed
sudo vim /etc/systemd/system/lg-queue.service
sudo vim /etc/systemd/system/looking-glass.service

# once the service files are adjusted to your needs, enable and start them
sudo systemctl enable lg-queue.service
sudo systemctl enable looking-glass.service
sudo systemctl start looking-glass.service
sudo systemctl start lg-queue.service

# looking glass should now be running on 127.0.0.1:8282
# set up a reverse proxy such as nginx / apache pointed to the above host
# and it should be ready to go :)

```

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