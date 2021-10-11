#!/bin/bash
#
# Installation script to setup and/or upgrade mirisim, the Python JWST MIRI Simulator.
# Running the installation script without parameters will install the latest 'stable' version
#
# Options:
#    --help
#      displays the help for this installation script
#    --test
#      install the tested development version
#    --clean
#      remove logfiles and tarfile
#    --update
#      remove existing installation and install the most recent version
#    --path
#      Installs the auxiliary data in the given path
#    --verbose
#      show all installed python packages at the end of the installation

mirisim_version="1.16"

# Some conda commands to make miricle work.
CONDA_PREFIX=$(conda info --base)
source $CONDA_PREFIX/etc/profile.d/conda.sh
conda config --remove channels http://ssb.stsci.edu/astroconda-dev/ 2>/dev/null
conda config --remove channels https://ssb.stsci.edu/astroconda 2>/dev/null
conda config --remove channels conda-forge 2>/dev/null

# Make it possible to print bold characters
bold=`tput bold`
normal=`tput sgr0`

# verboseEcho only prints the text if the verbose flag is used.
function verboseEcho {
  if [ -n "$verbose" ] ; then
    echo $1
  fi

  echo $1 >> $LOG/log.txt
}

# verboseEcho only prints the text if the verbose flag is used.
function echoLog {
  echo $1
  echo $1 | sed $'s,\x1b\\[[0-9;]*[a-zA-Z],,g'  | sed $'s,\x1b(B,,g' >> $LOG/log.txt
}

# checkInternet checks if a working internet connection is available and if curl/wget is installed.
function checkInternet {
  #
  # determine download method
  #
  internet=1
  jenkins=1
  which curl 1> /dev/null
  if [ $? = 0 ] ; then
    verboseEcho "Using curl to download packages."
    download="curl -O --silent -u miricle:$passwd "

    # Check for internet connection
    if curl --silent --head http://www.google.com/ | egrep "20[0-9] Found|30[0-9] Found|200 OK" >/dev/null
    then
      internet=1
    else
      internet=0
    fi

    # Determine whether www.miricle.org is up.
    if ! curl --silent --head https://jenkins.miricle.org>/dev/null; then
      jenkins=0
    fi
  else
    which wget 1> /dev/null
    if [ $? = 0 ] ; then
      verboseEcho "Using wget to download packages."
      download="wget -nd -q --user=miricle --password=$passwd "

      wget --spider -q http://www.google.com
      if [ "$?" != 0 ]; then
        internet=0
      fi

      wget --spider -q https://jenkins.miricle.org
      if [ "$?" != 0 ]; then
        jenkins=0
      fi
    fi
  fi

  if [ $internet -eq 0 ]; then
      echoLog "No internet connection found!"
      echoLog "Please rerun MIRICLE_install.bash with a working internet connection to install MIRICLE."
      exit
  fi

  verboseEcho "Internet connection found. Continuing the installation."

  if [ $jenkins -eq 0 ]; then
    echoLog "jenkins.miricle.org is down."
    echoLog "Please try to rerun MIRICLE_install.bash a little later."
    exit
  fi
  verboseEcho "jenkins.miricle.org is up and running."

  if [ -z "$download" ] ; then
    echoLog "Neither wget nor curl is present. Please have your system manager install either of them."
    exit
  fi
}

# Return status code of a comparison.
float_test() {
     echo | awk 'END { exit ( !( '"$1"')); }'
}

# checkUpdateOfScript checks if there is a newer version of the script available in GitHub.
function checkUpdateOfScript {
  verboseEcho ""
  verboseEcho "Checking if there is a newer version of the installation script available..."
  rm -f mirisim_install_version
  $download https://jenkins.miricle.org/install/mirisim/mirisim_install_version
  version_on_server=`cat mirisim_install_version`
  verboseEcho "Version of the used installation script is $mirisim_version. On the server, I found $version_on_server."
  uptodate=0
  float_test "$mirisim_version >= $version_on_server" && uptodate=1

  if [ "$uptodate" -eq 1 ]; then
    verboseEcho "No need to update the mirisim install script."
    rm -f mirisim_install_version
  else
    verboseEcho "Updating the mirisim install script."
    rm -f mirisim_install.bash
    rm -f mirisim_install_version
    $download https://jenkins.miricle.org/install/mirisim/mirisim_install.bash
    chmod +x mirisim_install.bash
    echoLog "mirisim installation script is updated."
    echoLog "Please rerun mirisim_install.bash to install mirisim."
    exit
  fi
}


# Check if anaconda is installed
function checkAnacondaInstalled {
  if hash conda 2>/dev/null; then
    verboseEcho ""
    verboseEcho "Anaconda is installed, continuing the installation."
  else
    echoLog ""
    echoLog "${bold}First install Anaconda python distribution: https://www.continuum.io/downloads${normal}"
    echoLog "If anaconda is already installed on your computer, execute"
    echoLog "  ${bold}conda activate base${normal}"
    exit
  fi
}

# Get the version number to install
function getVersionNumberToInstall {
  getVersion=0
  float_test "$version >= 9999999990" && getVersion=1

  if [ "$getVersion" -eq 1 ]; then
    verboseEcho "Requested installation of latest version from the $flavor track."
  else
    verboseEcho "Version number $version is given as parameter. Will try to install this version.";
  fi

  $download https://jenkins.miricle.org/mirisim/$flavor/buildNumbers

  while read line; do
    if [ -n "$line" ] ; then
      if [ $version -ge $line ]; then
        newversion=$line
      fi
      latestVersion=$line
    fi
  done < buildNumbers
  rm buildNumbers

  version=$newversion

  echoLog "${bold}Requested installation version $version of the $flavor track.${normal}"

  echoLog "Latest available $flavor version is $latestVersion."

  # Set the flavorName
  setFlavorName
  checkError ${PIPESTATUS[0]}

  # Check if we already have this version installed
  for env in `conda env list | grep mirisim$flavorName | awk 'NF>1{print $NF}'`
  do
    if [ -f $env/version ]; then
      alreadyInstalled=`sed "s/mirisim$flavorName //g" $env/version`
      if [[ $alreadyInstalled != *"mirisim"* ]]; then
        echoLog "Updating from version $alreadyInstalled"
        if [ "$version" -eq "$alreadyInstalled" ] ; then
          condaEnvName=`conda env list | grep "$env$" | awk '{print $1}'`
          echoLog "${bold}Requested installation version $version of the $flavor track is already installed in the $condaEnvName environment."
          echoLog ""
          echoLog "You can use it by executing the following command:"
          echoLog ""
          echoLog "conda activate $condaEnvName${normal}"
          echoLog ""
          read -p "Do you really want to reinstall this version? " -n 1 -r
          echo    # (optional) move to a new line
          if [[ ! $REPLY =~ ^[Yy]$ ]]
          then
            exit
          fi
        fi
      fi
    fi
  done
}

# Sets the flavor name
function setFlavorName {
  if [ $flavor = "stable" ] ; then
    flavorName=""
  else
    flavorName=".$flavor"
  fi
}

function checkError {
  if [ ! $1 -eq 0 ]; then
    printf "${bold}Installation failed!${normal}\n"
    echo "More information can be found in logfile: $LOG/log.txt"
    rm -f miricle-*-py*.0.txt
    exit
  fi
}

flavor="stable"
version="9999999999"
while [ "$1" != "" ]
do
   case $1 in
    "--help")
     echo "mirisim_install.bash is the installation script for mirisim, the simulator for the MIRI Instrument of JWST."
     echo ""
     echo "To be able to install mirisim, you need at the Anaconda python environment, at least version 4.2. You need the python 3 version."
     echo "You can download Anaconda from https://www.continuum.io/downloads"
     echo ""
     echo "Auxiliary data will be installed in \$HOME/mirisim. If you want to install this data in another location, you can set the MIRISIM_ROOT environment variable to this location, or you can use the --path option together with the script."
     echo ""
     echo "  --help"
     echo "      displays the help for this installation script."
     echo "  --test"
     echo "      installs a tested version of mirisim. This is not guaranteed to be stable or fully working."
     echo "  --clean"
     echo "      removes all old mirisim installations. Moves the current to *.todays_date and installs a new one"
     echo "  --verbose"
     echo "      show all installed python packages at the end of the installation."
     echo "  --version <version number>"
     echo "      installs the given version (or the latest successfull version before this)."
     echo "  --path <path location>"
     echo "      installs the auxiliary data in the given location."
     echo ""
     echo "This is version $mirisim_version of the mirisim_install.bash install script."
     exit
     ;;
    "--test")
     flavor="test"
     ;;
    "--clean")
     clean=1
     ;;
    "--verbose")
     verbose=1
     echo "Verbose mode"
     ;;
    "--version")
     version=$2
     shift
     ;;
    "--path")
     MIRISIM_ROOT=$2
     shift
     ;;
    *)
     echo "Invalid install option. Try with --help option to see the valid options."
     exit
     ;;
  esac
  shift
done

cwd=`pwd`

# Create and make a log file.
LOG=~/.mirisim/$flavor/`date +%y%m%d-%H%M%S`
mkdir -p $LOG

echoLog ""
echoLog "Installation logs found in ${bold}$LOG${normal}"
echoLog ""

# Check if there is a working internet connection
checkInternet
checkError ${PIPESTATUS[0]}

# Check if there is a newer version of the installation script
checkUpdateOfScript
checkError ${PIPESTATUS[0]}

# Check if anaconda is installed
checkAnacondaInstalled
checkError ${PIPESTATUS[0]}

# Set MIRISIM_ROOT
if [ -z "$MIRISIM_ROOT" ] ; then export MIRISIM_ROOT=$HOME/mirisim ; fi

# Check the version number to install
getVersionNumberToInstall
checkError ${PIPESTATUS[0]}

# Work around LC_CTYPE problem on MAC
LCCTYPE=$LC_CTYPE
unset LC_CTYPE

conda activate base
checkError ${PIPESTATUS[0]}

# Remove all old mirisim environments if the clean option is selected
if [ -n "$clean" ] ; then
  # Loop over all old mirisim environments
  verboseEcho "Removing all the old mirisim$flavorName anaconda environments"
  for env in `conda env list | grep mirisim$flavorName.2 | awk '{print $1}'`
  do
    echo "${bold}Removing $env${normal}"
    conda env remove -q --yes --name $env 2>&1 | tee -a $LOG/log.txt > /dev/null
    checkError ${PIPESTATUS[0]}
  done
fi

# Clone the existing conda environment and remove the conda environment which will be created.
# Check if we already have a mirisim installation
if [ `conda env list | cut -d' ' -f 1 | grep '^'mirisim$flavorName'$' | wc -l` -gt 0 ] ; then
  echoLog ""
  verboseEcho "Copy mirisim$flavorName to mirisim$flavorName.`date +%Y%m%d`"
  echoLog "${bold}Clone the old mirisim$flavorName environment${normal}"
  date=`date +%Y%m%d`
  if [ `conda env list | cut -d' ' -f 1 | grep '^'mirisim$flavorName.$date'$' | wc -l` -gt 0 ] ; then
    conda env remove -q --yes --name mirisim$flavorName.$date 2>&1 | tee -a $LOG/log.txt > /dev/null
  fi
  conda create --yes --name mirisim$flavorName.$date --clone mirisim$flavorName 2>&1 | tee -a $LOG/log.txt > /dev/null
  checkError ${PIPESTATUS[0]}
  verboseEcho "Remove the mirisim$flavorName python environment"
  conda env remove --yes --name mirisim$flavorName 2>&1 | tee -a $LOG/log.txt > /dev/null
  checkError ${PIPESTATUS[0]}
fi

# Check the operating system
if [[ "$OSTYPE" == "darwin"* ]]; then
  os="osx"
else
  os="linux"
fi

pythonVersion="27"
if [[ "$flavor" == "test" ]]; then
  if [[ $version -ge 33 ]]; then
    pythonVersion="37"
  elif [[ $version -ge 30 ]]; then
    pythonVersion="36"
  elif [[ $version -ge 16 ]]; then
    pythonVersion="35"
  fi  
fi
if [[ "$flavor" == "stable" ]]; then
  if [[ $version -ge 11 ]]; then
    pythonVersion="37"
  elif [[ $version -ge 10 ]]; then
    pythonVersion="36"
  elif [[ $version -ge 5 ]]; then
    pythonVersion="35"
  fi  
fi

if [[ $pythonVersion == "37" ]]; then
    echoLog "Creating base anaconda environment"
    $download https://jenkins.miricle.org/mirisim/$flavor/$version/conda_python_$os-stable-deps.txt
    conda create --yes --name mirisim$flavorName --file conda_python_$os-stable-deps.txt 2>&1 | tee -a $LOG/log.txt
    checkError ${PIPESTATUS[0]}
    conda activate mirisim$flavorName
    checkError ${PIPESTATUS[0]}
    rm conda_python_$os-stable-deps.txt

    echoLog "Install all dependencies"
    $download https://jenkins.miricle.org/mirisim/$flavor/$version/miricle-$os-deps.txt
    pip install -r miricle-$os-deps.txt
    checkError ${PIPESTATUS[0]}
    rm miricle-$os-deps.txt

    echoLog "Install miricle packages"
    $download https://jenkins.miricle.org/mirisim/$flavor/$version/miricle-$os-py$pythonVersion.0.txt
    chmod +x miricle-$os-py$pythonVersion.0.txt
    checkError ${PIPESTATUS[0]}

    ./miricle-$os-py$pythonVersion.0.txt 2>&1 | tee -a $LOG/log.txt
    checkError ${PIPESTATUS[0]}
    rm miricle-$os-py*.0.txt    
else
    verboseEcho "Downloading conda packages from https://jenkins.miricle.org/mirisim/$flavor/$version/miricle-$os-py$pythonVersion.0.txt"
    $download https://jenkins.miricle.org/mirisim/$flavor/$version/miricle-$os-py$pythonVersion.0.txt
    checkError ${PIPESTATUS[0]}

    echoLog "Creating the mirisim$flavorName conda environment"
    conda create --yes --name mirisim$flavorName --file miricle-$os-py*.0.txt 2>&1 | tee -a $LOG/log.txt
    checkError ${PIPESTATUS[0]}
    rm miricle-$os-py*.0.txt
fi

# Install the datafiles
if [ ! -d $MIRISIM_ROOT ]; then
  mkdir $MIRISIM_ROOT
fi

# Check the version of the files we need.
$download https://jenkins.miricle.org/mirisim/$flavor/$version/pysynphot_data
data_version=`cat pysynphot_data`
installData=0

# Compare the installed version with the version on the server
cmp -s pysynphot_data $MIRISIM_ROOT/pysynphot_data || installData=1
checkError ${PIPESTATUS[0]}

# Install the pysynphot data
if [[ "$installData" == "1" ]]; then
  echoLog "${bold}Installing the datafiles${normal}"
  rm -rf $MIRISIM_ROOT/cdbs
  cd $MIRISIM_ROOT
  $download https://jenkins.miricle.org/MIRICLE2/pysynphot_data/pysynphot_data-$data_version.tar.gz
  tar zxf pysynphot_data-$data_version.tar.gz
  rm -f pysynphot_dat*
  mv $cwd/pysynphot_data $MIRISIM_ROOT
else
  echoLog "pysynphot datafiles are already installed."
  rm $cwd/pysynphot_data
fi

conda activate mirisim$flavorName

# Write version number to the env directory
if [ -z ${CONDA_PREFIX+x} ]; then
  if [ -z ${CONDA_ENV_PATH+x} ]; then
    echo "";
  else
    echo mirisim$flavorName $version > $CONDA_ENV_PATH/version
  fi
else
  echo mirisim$flavorName $version > $CONDA_PREFIX/version
fi

rm -rf bioconda\:\: astropy\:\: http\:\:

echoLog ""
echoLog "To use the mirisim${flavorName} environment:"
echoLog " ${bold}export MIRISIM_ROOT=$MIRISIM_ROOT${normal}"
echoLog " ${bold}export PYSYN_CDBS=\$MIRISIM_ROOT/cdbs/${normal}"
echoLog ""
echoLog " ${bold}conda activate mirisim$flavorName${normal}"
echoLog ""
echoLog "Add these lines in your shell startup script (typically .bash_profile or .bashrc) to be able to run mirisim in the future."
echoLog "To switch back to the system python version:"
echoLog " ${bold}source deactivate${normal}"
echoLog ""
