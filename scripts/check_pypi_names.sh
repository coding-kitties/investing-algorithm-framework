#!/usr/bin/env bash
# Check PyPI availability for a list of candidate project names.
#
# Usage:
#   ./scripts/check_pypi_names.sh                   # check the built-in list
#   ./scripts/check_pypi_names.sh extra1 extra2     # also check extra names
#   ./scripts/check_pypi_names.sh --only NAME ...   # check ONLY the args
#   ./scripts/check_pypi_names.sh -o results.txt    # write to a specific file
#
# Output:
#   By default writes a timestamped report under
#   scripts/pypi_name_reports/pypi-names-YYYYMMDD-HHMMSS.txt
#   plus split .available.txt / .taken.txt / .errors.txt sidecar files.
#   Pass -o/--output PATH to override the main output file.
#
# Notes:
# - PyPI returns 404 for unknown packages, 200 for taken ones.
# - "Available" on PyPI does not guarantee you can actually register the
#   name (PEP 541 / squatting rules / typo-confusion). Always do a manual
#   sanity check on the top picks.

set -uo pipefail

# ---------------------------------------------------------------------------
# Built-in candidate list. Add freely. Keep one name per line.
# ---------------------------------------------------------------------------
read -r -d '' BUILTIN_NAMES <<'EOF' || true
# --- forge family --------------------------------------------------------
tradeforge
stratforge
tickforge
algoforge
quantforge
signalforge
backforge
finforge
vecforge
strategyforge
portforge
orderforge

# --- bench family --------------------------------------------------------
tickbench
quantbench
finbench
backbench
stratbench
algobench
tradebench
vecbench
sigbench

# --- loop family ---------------------------------------------------------
quantloop
algoloop
tradeloop
tickloop
signalloop
finloop
vecloop
backloop
stratloop
eventloop-trader

# --- vec / vector family -------------------------------------------------
vectrade
algovec
quantvec
tradevec
backvec
stratvec
vecquant
vecalgo
vecstrat
vecbacktest

# --- kit family (mostly taken but try variants) --------------------------
pyfinkit
tradekit-py
quantkit-py
backkit
stratkit
signalkit
finkit-py

# --- lab family ----------------------------------------------------------
kittylab
quantlab-py
tradelab-py
stratlab-py
algolab-py
backlab
finlab-py
signlab

# --- nest family ---------------------------------------------------------
tradenest
quantnest
nestquant
nestalgo
nesttrade

# --- ops family ----------------------------------------------------------
tradeops
algoops
quantops
stratops
backops

# --- coding-kitties brand-aligned ---------------------------------------
kittyquant
kittyalgo
algokitty
quantcat
tradecat
catquant
cattrade
meowquant
pawquant
algopaws
tradepaws
quantpaws
paws-algo
purrquant
purralgo
purrtrade
clawquant
clawtrade
nineliveskit
felinequant
prowlquant
prowltrade
pouncequant
pouncetrade
whiskerquant

# --- short / standalone --------------------------------------------------
quantmew
ticktape
tapequant
ledgerquant
parlay
parlay-quant
sentinelquant
beaconquant
beacontrade
lighthousequant
compassquant
compasstrade
helmquant
helmtrade
mastquant
keelquant
anchorquant
buoyquant
tideloop
tidequant

# --- portmanteaus / fresh -----------------------------------------------
algora
algoria
quantara
quantora
tradera
backtra
strata-py
stratera
signalia
quantelle
algoria-py

# --- strategy / signal centric ------------------------------------------
strategyloop
strategybench
strategynest
signalbench
signalnest
signalvec
sigforge

# --- trade / order / portfolio centric ----------------------------------
orderbench
orderloop
orderforge
portfoliolab
portfolioloop
portfoliobench
positionforge

# --- python-prefixed (last resort) --------------------------------------
pyalgotrade-ng
pyquant-framework
pytradeforge
pyquantforge
pyquantbench

# --- user-suggested batch (May 2026) ------------------------------------
algoforge
quantflow
stratify
alphaworks
alphatrader
pytrader
tradex
tradecore
quantcore
pytradebotlab
quantlab
quantcraft
tradecraft
tradealchemy
pytrade
fluxtrade
tradelib
quantify
alphatrade
coretrade
pyquant
tradelab
traderlib
fluxquant
tradeworks
quantlib
tradebotlab
quantbotlab
stratatrade
qlynk
toro
prysm
vyn
arvo
delta
fluxis
sivo
corex
numa
aerith
drift
orium
kaltra
spire
vetra
nebula
orionis
xylo
lunara
alchemy
craft
axion
nexora
omnitrade
lumora
veltrix
equinox
zenith
orbis
cypherion
novatrade
optivest
athenium
vertex
arbitrix
quantis
finetix
modulus
algosphere
kintara
codetrade
neuratrade
alphatrail
tradevibe
signalwave
flowalgo
marketforge
apexquant
vectortrade
profitsense
chronotrade
quantix

# --- mega expansion (May 2026) ------------------------------------------
# Trading / market metaphors
candletrade
candleforge
candlebench
candleloop
ohlc-forge
ohlcforge
bidaskforge
spreadforge
spreadquant
slippagelab
fillforge
makerforge
takerforge
bookforge
orderbookforge
orderbookloop
orderbooklab
limitforge
marketmaker-py
mm-forge
liquidityforge
liquidityquant
volatilityforge
volaforge
volaquant
gammaforge
deltaforge
thetaforge
vegaforge
greeksforge
hedgeforge
hedgequant
arbforge
arbquant
arblab
arbitrageloop
mevquant
basisforge
basisquant
carryforge
carryquant
momentumforge
momentumloop
trendforge
trendquant
trendloop
meanreverter
revertquant
breakoutforge
breakoutquant

# Compound: <verb>-trade / <verb>-quant
runquant
runforge
runtrader
runalgo
forgequant
forgealgo
forgetrade
benchquant
benchalgo
benchtrade
benchforge
loopquant
looptrade
loopalgo
loopforge
nestbench
labquant
labtrade
labforge
labalgo

# Bot / agent flavour
algobot-py
quantbot-py
tradebot-py
botforge
botbench
botlab
botloop
botquant
quantagent
tradeagent
algoagent
strategyagent
agentforge
agenttrade
agentquant
swarmquant
swarmtrade

# Lab / studio / workshop
tradestudio
quantstudio
algostudio
stratstudio
backstudio
signalstudio
strategystudio
quantworkshop
tradeworkshop
algoatelier
quantatelier
tradeatelier

# Engine
algoengine
quantengine
tradeengine
backengine
stratengine
signalengine
vecengine
strategyengine
tickengine
orderengine
portengine
portfolioengine
fillengine

# Suite / kit / pack
algosuite
quantsuite
tradesuite
stratsuite
backsuite
signalsuite
quantpack
tradepack
algopack
stratpack
backpack-quant
finpack
finsuite

# Stream / pipeline
quantstream
tradestream
algostream
signalstream
tickstream
quantpipeline
tradepipeline
algopipeline
signalpipeline
tickpipeline

# Mythic / sci-fi / abstract
oraclequant
oracletrade
sigil
sigilquant
sigiltrade
runic
runiquant
arcanaquant
arcanetrade
solstice
solsticequant
zephyrquant
zephyrtrade
auroraquant
auroratrade
nimbusquant
nimbustrade
cinder
cindertrade
emberquant
embertrade
forgequant
hyperionquant
hyperiontrade
oryx
oryxquant
mosaicquant
mosaictrade
prismquant
prismtrade
nautilus-trade
chimera-quant
chimeratrade
phoenixquant
phoenixtrade
dragonquant
dragontrade
falconquant
falcontrade
ravenquant
raventrade
hawkquant
hawktrade
owlquant
owltrade
wolfquant
wolftrade
foxquant
foxtrade
otterquant
ottertrade
beaverquant
beavertrade
lynxquant
lynxtrade
puma-quant
pumatrade
tigerquant
tigertrade
pandaquant
pandatrade
sealquant
sealtrade

# Speed / motion
swiftquant
swifttrade
boltquant
bolttrade
dashquant
dashtrade
sprintquant
sprinttrade
turbotrade
turboquant
rocketquant
rockettrade
warpquant
warptrade

# Geometry / structure
prismforge
prismbench
gridquant
gridforge
gridtrade
latticequant
latticetrade
mosaicforge
helixquant
helixtrade
helixforge
spiralquant
spiraltrade
arcquant
arctrade
arcforge

# Time / chronology
chronoforge
chronoquant
chronobench
chronoloop
epochquant
epochtrade
epochforge
ticktockquant
secondsquant

# Energy / power
voltquant
volttrade
amperequant
amperetrade
fluxforge
fluxbench
fluxloop
sparkquant
sparktrade
sparkforge
ignitequant
ignitetrade
emberforge
infernoquant
infernotrade

# Foundations / minimalism
core-quant
quantcore-py
tradecore-py
quantbase
tradebase
algobase
stratbase
backbase
quantroot
traderoot
quanthub
tradehub
algohub
strathub
backhub

# Pure made-up (1-2 syllables, brandable)
zyra
zyrik
zyrex
ryze
ryven
nuvo
nuvix
luma
lumix
vexa
vexar
vexor
sona
sonar-quant
korva
korvix
xelva
xelvix
vyra
vyran
arval
arvik
brava
brovo
calix
caliz
cylex
darv
darvix
elara
elarix
falix
firra
glym
glyph
glyphquant
hera-quant
ignix
jaxa
kelix
lirex
lyra-quant
miro
moxa
norix
oryxquant
pixa
qyra
qyrix
rixa
sava
talix
tarsa
ulva
varix
vexa
xandra
yara-quant
zora
zola
zolium
zylar

# --- mega expansion #2 (May 2026) ---------------------------------------
# Word + suffix combos still missing
quantbridge
tradebridge
algobridge
stratbridge
quantharbor
tradeharbor
quantanchor
quantcompass
quantnest-py
algonest-py
quantcanvas
tradecanvas
quantmosaic
quantblueprint
tradeblueprint
quantatlas
tradeatlas
quantroute
traderoute
quantvault
tradevault
algovault
stratvault
quantcache
quanttrack
tradetrack
algotrack
quantradar
traderadar
quantbeacon
tradebeacon
quantgrove
quantorchard
quantroost
quantburrow
quantden

# Real animals (less-used in fintech)
otterquant
otterforge
foxlab
foxbench
badgerquant
badgertrade
heronquant
herontrade
mantaquant
mantatrade
orcaquant
orcatrade
sablequant
sabletrade
mongoquant
mongotrade
ferretquant
ferrettrade
weaselquant
weaseltrade
caracalquant
caracaltrade
ocelotquant
ocelottrade
servalquant
servaltrade
margayquant
margaytrade
linxquant
linxtrade
jaguarquant
jaguartrade
leopardquant
leopardtrade
cheetahquant
cheetahtrade
caracal-py
serval-py
ocelot-py
margay-py
manul
manul-py
manulquant
manultrade
pallasquant
pallastrade
sandcatquant
sandcattrade

# Tools / instruments / sailing
quantcompass
quantsextant
sextantquant
sextantforge
quantmariner
mariner-quant
quanthelm
quantcompasspy
trimtab
trimtabquant
trimtabtrade
gunwale
gunwale-quant
yardarm
yardarm-quant
boomquant
keelhaul
keelhaulquant
fathomquant
fathomtrade
plumblinequant
plumbquant
plumbtrade

# Smithing / metallurgy
quantanvil
anvilquant
anviltrade
forgeworks
quantforger
tradeforger
algoforger
stratforger
sigforger
ironforge-quant
steelquant
steeltrade
goldquant-py
silverquant-py
brassquant
brasstrade
bronzequant
bronzetrade
copperquant
coppertrade
ingotquant
ingottrade

# Architecture / construction
quantbeam
quantkeystone
keystonequant
keystonetrade
keystoneforge
quantgirder
quantbuttress
quantfoundation
foundationquant
foundationtrade
quantframework2
quantscaffold
scaffoldquant
quantbluepr

# Lab / science
quantcatalyst
catalystquant
catalysttrade
catalyzealgo
quantbeaker
quantflask
quantburette
quantcrucible
crucible-quant
crucibletrade
quantatomic
atomicquant
atomictrade

# Greek / Latin roots
quantmeta
metaquant-py
quantnova
novaquant
novatraderpy
quantastra
astraquant
astratrade
quantcosma
cosmaquant
quantethera
quantsolaris
solarisquant
quantelectron
quantphoton
photonquant
photontrade
quantkinetic
kineticquant
kinetictrade
quantvortex
vortexquant
vortextrade
quantpulsar
pulsarquant
pulsartrade
quantnebulae
nebulaquant
nebulatrade
quantgalaxis
galaxisquant
quantorion
orionquant
oriontrade
quantcassio
cassioquant
quantvega
vegaquant
vegatrade
quantsirius
siriusquant
quantpolaris
polarisquant
polaristrade

# Compound English (real-word feel)
clearbet
clearbet-quant
quanttide
tidequant-py
quantcurrent
currentquant
quantripple
ripplequant
quantwake
wakequant
quantsurge
surgequant
surgetrade
quantcrest
crestquant
crestrade
quantebb
ebbquant
quantflow-py
quantebbquant
quantbreaker
breakerquant

# Mythology / folklore
quanthermes
hermesquant
hermestrade
quantapollo
apolloquant
apollotrade
quantarea
quantares
aresquant
quantatlas2
quantatlas-py
quantminerva
minervaquant
minervatrade
quantvulcan
vulcanquant
vulcantrade
quantnyx
nyxquant
nyxtrade
quanteros
erosquant
quantselene
selenequant
selenetrade
quantheliox
helioxquant
quantmidas
midasquant
midastrade
quantfreya
freyaquant
freyatrade
quantodin
odinquant
odintrade
quantloki
lokiquant
lokitrade
quantthor
thorquant
thortrade
quantbalder
balderquant
quanttyr
tyrquant
quanthel
helquant
quantsleipnir
sleipnirquant
quantyggdrasil
yggdrasilquant
yggdrasiltrade

# Card / dice / poker (markets-as-game)
quantante
antequant
quantbluff
bluffquant
blufftrade
quantchip
chipquant
chiptrade
quantdeck
deckquant
decktrade
quantparlay
parlayquant
parlaytrade
quantwager
wagerquant
wagertrade
quantbankroll
bankrollquant
quanttable
tablequant
tabletrade
quantedge
edgequant
edgetrade
quantkelly
kellyquant
kellytrade
quanthand
handquant
quantturn
turnquant

# Money / finance vocabulary
quantbasis
quantcurry
curryquant
quantyield
yieldquant
yieldtrade
yieldforge
quantcoupon
couponquant
quantnotional
notionalquant
notionalforge
quantnominal
quantfutures
quantforward
forwardquant
forwardtrade
quantswap
swapquant
swaptrade
quantfx
fxquant
fxtrade-py
quantcrypto
cryptoquant-py
cryptotradepy
quantequity
equityquant
equitytrade
quantbond
bondquant
bondtrade
quantcommodity
commodityquant
commoditytrade

# Compounds with -lab / -studio / -works (newer slots)
candlelab
candlestudio
candleworks
orderlab
orderstudio
orderworks
fillstudio
fillworks
filllab
liquiditylab
liquiditystudio
liquidityworks
hedgelab
hedgestudio
hedgeworks
arbstudio
arblab2
arbworks
mevlab
mevstudio
mevworks

# Dutch / Belgian (your locale)
handelaar
handelaar-py
beleg
belegger
belegquant
beursquant
beurstrade
koersquant
koerstrade
markttrade
marktquant
fondsquant
fondstrade
trader-nl
strategienl

# Verb-y action names
striker-quant
strikerquant
strikertrade
volleyquant
volleytrade
pivotquant
pivottrade
swingquant
swingtrade-py
swivelquant
sweepquant
sweeptrade
shoutquant
relayquant
relaytrade

# Made-up brand names round 2
zentro
zentrix
zenari
zaltra
zarvix
yorvik
yarnex
xanto
xanos
wexa
wexor
volaris-quant
volaris
veno
veora
veric
vexum
trix-quant
trovix
trovo
tovan
toraq
tonari
sylvex
sylas-quant
sylas
solvix
solven
sigron
sigrix
selvix
selvar
sarven
sarix
ralva
ralix
qorvex
qorva
qoltra
qoltrix
provix
proven-quant
provo
prelix
plora
plora-quant
plenix
plencore
phylo-quant
peora
oxen-quant
oxenquant
oxentrade
omari-quant
omari
nyxa
nyrix
nyran
novix
nordax
nordax-quant
nivex
nimora
nimari
nilara
nicor
neuvo
neuvix
narvix
narva
mythra
myrex
myra-quant
myralis
myrali
muvix
moxar
moxari
modus-quant
mirex
mirava
mirava-quant
miran
maxara
matrix-quant
marvix
marva
maeva-quant
maeva
luvix
lurex
lumin-quant
lumix-quant
lurix
luxora
luxar
lorvix
lorvik
loraq
loram
lirix
linara
liera
liana-quant
levix
levaris
levanta
lenix
lenara
lemora
lekara
laxara
latrix
larvix
larva-quant
laorvix
laorix
laniqua
lanira
landora
lairex
kyrix
kyrian
kyran-quant
kyran
kyora
kovara
kovan
korvix-quant
koltra
koltar
koalitra
kithara-quant
kithara
kithar
kineris
kethra
kerala-quant
kerala
karva
karthos
karoq-quant
karoq
karith
kalvix
kaltrix
kaiora
kairos-quant
kairos
jurix
joran
jolva
jolari
jolan
jevex
jaxora
jax-quant
ivex
ivara
istra-quant
istra
isora
iolar
inara-quant
inara
ilara
iesto
hyvex
hyran
hyora
hovix
horvix
horvath-quant
horos
honara
honari
honar
holvex
holvar
holvan
holari
hivar
hilara
hilar
heya-quant
hexan
hetvix
hesia
herox
heliox-quant
helix-quant
heliana
helara
hayara
hatvix
harvix
hari-quant
halvar
halvan
gyrex
gyran
gyora
gylo
gyaru-quant
gravix
grava
goran-quant
goran
glyvex
glyran
gloria-quant
glora
glivar
gleaf
glade-quant
ginara
ginar
gilara
gilar
geura
gerix
geova
geno-quant
gemix
gelvix
geltra
gelara
geara
fyrex
fyran
fyora
furvix
furora
furian
funara
funar
fulvar
fulara
fulan
fritex
freva
fresia-quant
fresia
frenia
fralix
forvex
forvar
foran-quant
foran
fonara
folvix
foliar-quant
foliar
flovex
flora-quant
flixar
flevix
fleva
flara-quant
flara
fizan
fioral
fiona-quant
finvex
finvar
finlara
filora
felvix
feltora
felipa-quant
felipa
fela
fariq
faran-quant
faran
fanora
falvix
falva
falor
exora-quant
exora
evoria
evoran
evara
etora
estro-quant
estro
ervina
eryx-quant
eryx
ervix
erunix
ertra
ertan
erris
erlux
erlina
eridia
ergon-quant
ergon
erge
erebus-quant
erebus
era-quant
epona-quant
epona
elvex
elvarin
elvar
elura-quant
elura
elnar
ellaria
elka
elixir-quant
elios
elaris
edovix
edolva
edora
ecora
ebon-quant
ebon
duvex
duran-quant
duran
dorian-quant
dorian
dorain
donara
donar
domara
dolva
dolari
divan-quant
divan
ditra
dirvix
dirvar
dimora-quant
dimora
diliana
dilara-quant
dilara
delvix
delvar
delan
deira
dax-quant
darvix-quant
daron
daric
darian-quant
darian
daluvian
dalvor
dalvar
daloran
dakara
cyrene-quant
cyrene
cyno-quant
cyno
cylix
cyana
cyala
cusora
cusan
curlivar
curio-quant
curio
covix
covara
corvix-quant
corvex
corian-quant
corian
copia-quant
copia
contari
conar
colvix
colveran
colvar
colora-quant
cobalt-quant
cobalt
cinora
cineara
cilora
celvix
celvar
celiana
celar
cedric-quant
cedric
cavorix
cavoran
cavi
caston
casora
casio-quant
casio
caron-quant
caron
caribel
cariana
carat-quant
carat
caplan-quant
caplan
caora
cantor-quant
cantor
canora
calvix
calvar
calixa
calida
caleon
calax
cadexa
cadana
byzar
byvar
byran-quant
byran
butera
busara
bursa-quant
bursa
brevix
breva
bral
bovix
bortax
boran-quant
boran
bonvex
bonvar
bonari
boli-quant
boli
bohan-quant
bohan
bohama
boavix
blix
blax-quant
blax
blara
biora
binara
bilora
bilar
bevix
beva
betora
besta-quant
besta
besar
benara
beltra
beltan
belka
belan
beira-quant
beira
bayan-quant
bayan
bavix
bavar
bavan
basora
banora
balura
balux
balira
bahira-quant
bahira
azora
azlin
aziora
ayora
ayata
avorix
avoran
avinor
avier
avalon-quant
avalon
ausora
auran-quant
auran
aurica
auralis
arwen-quant
arwen
arvox
arvina
arrowquant
arquera
ariora
aria-quant
aren-quant
aren
araq
aqolva
aqola
apoth-quant
apoth
apex-quant-py
aova
anvar-quant
anvar
antora
anova-quant
anova
anara-quant
anara
amora-quant
amora
amaira
alvina
altar-quant
altar
alora-quant
alora
alex-quant
alex-quant-py
alar
akira-quant
akira
ailura
ailar
ahmar
agora-quant
agora
afora
adara-quant
adara
EOF

# Parse args ---------------------------------------------------------------
ONLY_ARGS=0
OUTPUT_FILE=""
EXTRA_NAMES=()
while [[ $# -gt 0 ]]; do
    arg="$1"
    case "$arg" in
        --only) ONLY_ARGS=1 ;;
        -o|--output)
            shift
            OUTPUT_FILE="${1:-}"
            if [[ -z "$OUTPUT_FILE" ]]; then
                echo "Error: --output requires a path argument" >&2
                exit 2
            fi
            ;;
        --output=*) OUTPUT_FILE="${arg#--output=}" ;;
        -h|--help)
            sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) EXTRA_NAMES+=("$arg") ;;
    esac
    shift
done

# Default output file (timestamped) if none supplied -----------------------
if [[ -z "$OUTPUT_FILE" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    REPORTS_DIR="$SCRIPT_DIR/pypi_name_reports"
    mkdir -p "$REPORTS_DIR"
    OUTPUT_FILE="$REPORTS_DIR/pypi-names-$(date +%Y%m%d-%H%M%S).txt"
fi

# Build final candidate list ----------------------------------------------
declare -a NAMES
if [[ "$ONLY_ARGS" -eq 0 ]]; then
    while IFS= read -r line; do
        # strip comments / blank lines / surrounding whitespace
        line="${line%%#*}"
        line="${line//$'\r'/}"
        line="$(echo "$line" | tr -d '[:space:]')"
        [[ -z "$line" ]] && continue
        NAMES+=("$line")
    done <<< "$BUILTIN_NAMES"
fi
NAMES+=("${EXTRA_NAMES[@]+"${EXTRA_NAMES[@]}"}")

# De-duplicate, preserve order --------------------------------------------
declare -a UNIQUE
SEEN_KEYS=" "
for n in "${NAMES[@]}"; do
    key="$(echo "$n" | tr '[:upper:]' '[:lower:]')"
    case "$SEEN_KEYS" in
        *" $key "*) ;;
        *)
            SEEN_KEYS="$SEEN_KEYS$key "
            UNIQUE+=("$n")
            ;;
    esac
done

if [[ "${#UNIQUE[@]}" -eq 0 ]]; then
    echo "No names to check." >&2
    exit 1
fi

echo "Checking ${#UNIQUE[@]} names against PyPI..." >&2
echo >&2

# Query PyPI ---------------------------------------------------------------
TMP_AVAIL="$(mktemp)"
TMP_TAKEN="$(mktemp)"
TMP_ERR="$(mktemp)"
trap 'rm -f "$TMP_AVAIL" "$TMP_TAKEN" "$TMP_ERR"' EXIT

check_one() {
    local name="$1"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 \
        "https://pypi.org/pypi/${name}/json")
    case "$code" in
        404) echo "$name" >> "$TMP_AVAIL" ;;
        200) echo "$name" >> "$TMP_TAKEN" ;;
        *)   echo "$name ($code)" >> "$TMP_ERR" ;;
    esac
}

# Run checks in parallel (cap concurrency to be polite to PyPI).
MAX_PARALLEL=8
i=0
for name in "${UNIQUE[@]}"; do
    check_one "$name" &
    ((i++))
    if (( i % MAX_PARALLEL == 0 )); then
        wait
    fi
done
wait

# Report -------------------------------------------------------------------
AVAIL_COUNT=$(wc -l < "$TMP_AVAIL" | tr -d ' ')
TAKEN_COUNT=$(wc -l < "$TMP_TAKEN" | tr -d ' ')
ERR_COUNT=0
if [[ -s "$TMP_ERR" ]]; then
    ERR_COUNT=$(wc -l < "$TMP_ERR" | tr -d ' ')
fi

{
    echo "PyPI name availability report"
    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "Total checked: ${#UNIQUE[@]}"
    echo "  Available:   $AVAIL_COUNT"
    echo "  Taken:       $TAKEN_COUNT"
    echo "  Errors:      $ERR_COUNT"
    echo

    echo "============================================================"
    echo "AVAILABLE on PyPI ($AVAIL_COUNT):"
    echo "============================================================"
    sort -u "$TMP_AVAIL"

    echo
    echo "============================================================"
    echo "TAKEN on PyPI ($TAKEN_COUNT):"
    echo "============================================================"
    sort -u "$TMP_TAKEN"

    if [[ -s "$TMP_ERR" ]]; then
        echo
        echo "============================================================"
        echo "ERRORS / unexpected status ($ERR_COUNT):"
        echo "============================================================"
        sort -u "$TMP_ERR"
    fi
} > "$OUTPUT_FILE"

# Also write split files alongside for easy grepping ----------------------
OUTPUT_DIR="$(dirname "$OUTPUT_FILE")"
OUTPUT_BASE="$(basename "$OUTPUT_FILE" .txt)"
sort -u "$TMP_AVAIL" > "$OUTPUT_DIR/${OUTPUT_BASE}.available.txt"
sort -u "$TMP_TAKEN" > "$OUTPUT_DIR/${OUTPUT_BASE}.taken.txt"
if [[ -s "$TMP_ERR" ]]; then
    sort -u "$TMP_ERR" > "$OUTPUT_DIR/${OUTPUT_BASE}.errors.txt"
fi

# Console summary ----------------------------------------------------------
echo "Done."
echo "  Total checked: ${#UNIQUE[@]}"
echo "  Available:     $AVAIL_COUNT"
echo "  Taken:         $TAKEN_COUNT"
if (( ERR_COUNT > 0 )); then
    echo "  Errors:        $ERR_COUNT"
fi
echo
echo "Wrote:"
echo "  $OUTPUT_FILE"
echo "  $OUTPUT_DIR/${OUTPUT_BASE}.available.txt"
echo "  $OUTPUT_DIR/${OUTPUT_BASE}.taken.txt"
if [[ -s "$TMP_ERR" ]]; then
    echo "  $OUTPUT_DIR/${OUTPUT_BASE}.errors.txt"
fi
