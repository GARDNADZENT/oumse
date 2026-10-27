# -*- coding: utf-8 -*-
"""
oumse_brom_session_runner.py - Runner BROM PERSISTANT
======================================================
A PLACER dans le dossier mtkclient (a cote de mtk.py). Lance avec Python 64 bits.

Maintient UNE SEULE connexion BROM/DA ouverte et accepte des commandes JSON sur
stdin. Permet d'enchainer read/write/erase sur plusieurs partitions SANS que le
telephone reboot ou se deconnecte entre les operations (comme CM2/TSM Tool).

Protocole stdin (une commande = une ligne JSON) :
    {"op":"read",   "part":"proinfo", "out":"C:/.../proinfo.bin"}
    {"op":"write",  "part":"proinfo", "in" :"C:/.../proinfo.bin"}
    {"op":"erase",  "parts":["frp","metadata"]}     # liste -> multi-erase
    {"op":"reboot"}        # reboot le tel et termine la session
    {"op":"quit"}          # ferme proprement sans reboot

Reponses sur stdout (lignes preflxees OUMSE_*) :
    OUMSE_STEP:<libelle>           debut d'une etape
    OUMSE_READY:<json>             apres connexion : {chip, partitions:[{name,size}...]}
    OUMSE_OK:<op>[:<details>]      operation reussie
    OUMSE_FAIL:<op>:<detail>       operation echouee
Les autres lignes sont la sortie brute mtkclient (filtree cote tool).
"""
import os
import sys
import json
import logging
import argparse
import time

# ============================================================================
# MONKEY-PATCH pyserial Windows (AVANT import mtkclient)
# ============================================================================
# Probleme : pendant l'upload DA stage 1 sur MTK (mode preloader VCOM), le
# device USB change de configuration interne. pyserial appelle SetCommState()
# pour reconfigurer le port -> Windows renvoie ERROR_GEN_FAILURE (31) ->
# PermissionError(13) "Un peripherique attache au systeme ne fonctionne pas
# correctement" -> "Cannot configure port" -> "Error on sending DA".
#
# TFM/AMT/UnlockTool n'ont pas ce souci avec le driver MTK standard car ils
# n'utilisent PAS pyserial : ils ont un wrapper Win32 maison qui retry
# automatiquement sur cette erreur transitoire.
#
# On reproduit le meme comportement : on wrap pyserial._reconfigure_port pour
# retry jusqu'a 5x avec 50ms entre, ce qui laisse le device se stabiliser.
#
# v2 (18/09) : RETRY SEUL NE SUFFIT PAS.
#   Constat terrain : apres "Jumping to 0x200000", le telephone se REENUMERE.
#   Le port COM du preloader DISPARAIT et une nouvelle interface (DA) apparait,
#   parfois sous un AUTRE numero de COM. Reconfigurer un descripteur mort ne
#   peut pas marcher, quel que soit le nombre de retries : il faut FERMER et
#   ROUVRIR, et si le port a change de nom, ROUVRIR SUR LE NOUVEAU.
#   C'est ce que font les outils commerciaux avec leur wrapper Win32 maison.
#
#   Variables d'environnement :
#     OUMSE_SERIAL_REOPEN=0  -> desactive la reouverture (ancien comportement)
#     OUMSE_SERIAL_TRIES=N   -> nombre de tentatives (defaut 6)
_MTK_VIDS = (0x0E8D, 0x1004, 0x22D9, 0x0FCE)


def _scan_mtk_com(exclude=None):
    """Nom du premier port COM MediaTek present, hors 'exclude'."""
    try:
        import serial.tools.list_ports as _lp
    except Exception:
        return None
    for p in _lp.comports():
        if exclude and p.device == exclude:
            continue
        desc = (getattr(p, "description", "") or "").lower()
        if (getattr(p, "vid", None) in _MTK_VIDS or "preloader" in desc
                or "vcom" in desc or "mediatek" in desc or "usb serial" in desc):
            return p.device
    return None


try:
    import serial
    try:
        import serial.serialwin32 as _sw32
        _orig_reconfigure = _sw32.Serial._reconfigure_port
        # v3 : le port ne disparait pas sur ce modele (verifie au moniteur),
        # donc fermer/rouvrir ne sert a rien et peut nuire -> desactive.
        _REOPEN = os.environ.get("OUMSE_SERIAL_REOPEN", "0") != "0"
        try:
            _TRIES = max(2, int(os.environ.get("OUMSE_SERIAL_TRIES", "6")))
        except Exception:
            _TRIES = 6

        def _patched_reconfigure(self, *args, **kwargs):
            # garde anti-recursion : self.open() rappelle _reconfigure_port
            if getattr(self, "_oumse_busy", False):
                return _orig_reconfigure(self, *args, **kwargs)
            last_err = None
            for attempt in range(_TRIES):
                try:
                    return _orig_reconfigure(self, *args, **kwargs)
                except (PermissionError, OSError) as e:
                    last_err = e
                    time.sleep(0.05 * (attempt + 1))
                    # a partir de la 3e tentative, le port est probablement MORT
                    # (le peripherique s'est reenumere) : on rouvre.
                    if _REOPEN and attempt >= 2:
                        self._oumse_busy = True
                        try:
                            old = getattr(self, "port", None)
                            try:
                                self.close()
                            except Exception:
                                pass
                            time.sleep(0.25)
                            # 1) meme port
                            try:
                                self.open()
                                sys.stderr.write(
                                    "[oumse] port %s rouvert\n" % old)
                                sys.stderr.flush()
                                return
                            except Exception:
                                pass
                            # 2) le peripherique est revenu sous un AUTRE COM
                            for _ in range(20):          # ~5 s d'attente
                                new = _scan_mtk_com(exclude=None)
                                if new and new != old:
                                    try:
                                        self.port = new
                                        self.open()
                                        sys.stderr.write(
                                            "[oumse] port change %s -> %s\n"
                                            % (old, new))
                                        sys.stderr.flush()
                                        return
                                    except Exception:
                                        pass
                                time.sleep(0.25)
                        finally:
                            self._oumse_busy = False
            # Dernier recours : on log et on swallow (comportement d'origine).
            try:
                sys.stderr.write(
                    "[oumse] _reconfigure_port swallow apres %d retries: %s\n"
                    % (_TRIES, str(last_err)[:120]))
                sys.stderr.flush()
            except Exception:
                pass
        _sw32.Serial._reconfigure_port = _patched_reconfigure
        sys.stderr.write("[oumse] pyserial _reconfigure_port patched v2 "
                         "(reopen=%s, tries=%d)\n" % (_REOPEN, _TRIES))
        sys.stderr.flush()
    except Exception as _e:
        sys.stderr.write("[oumse] pyserial patch skip: " + str(_e)[:80] + "\n")
        sys.stderr.flush()
except ImportError:
    pass

try:
    from mtkclient.config.mtk_config import MtkConfig
    from mtkclient.Library.mtk_class import Mtk
    from mtkclient.Library.DA.mtk_da_handler import DaHandler
    from mtkclient.Library.mtk_main import ArgHandler
except Exception as e:
    print("OUMSE_FAIL:import:" + str(e), flush=True)
    sys.exit(1)

# ============================================================================
# RECONNEXION SERIE APRES LE SAUT DU DA
# ============================================================================
# Constat en lisant seriallib.py : SerialClass.connect() n'est appele QU'UNE
# FOIS, au debut. Apres "Jumping to 0x200000" le telephone se reenumere ; le
# serial.Serial garde en main un descripteur mort et mtkclient lit dans le
# vide jusqu'au timeout. Il n'existe aucune logique de reconnexion.
#
# On en ajoute une : quand une lecture ne rend rien ET que le port COM qu'on
# tient a DISPARU de la machine, on ferme, on attend le nouveau port MediaTek
# et on rappelle connect(). detectdevices() accepte deja le PID 0x2001 (DA),
# donc il retrouvera l'appareil tout seul.
#
#   OUMSE_SERIAL_RECONNECT=0  -> desactive ce comportement
# v3 (18/09) : la chronologie des ports a montre que COM7 NE DISPARAIT PAS
# apres le saut. Cette reconnexion est donc inutile ici -> DESACTIVEE par
# defaut. On la garde pour les modeles qui, eux, se reenumerent.
#   OUMSE_SERIAL_RECONNECT=1 -> reactive
_RECONNECT = os.environ.get("OUMSE_SERIAL_RECONNECT", "0") != "0"
try:
    _RC_WAIT = max(2.0, float(os.environ.get("OUMSE_SERIAL_RECONNECT_WAIT", "8")))
except Exception:
    _RC_WAIT = 8.0

if _RECONNECT:
    try:
        from mtkclient.Library.Connection.seriallib import SerialClass as _SC

        def _port_present(name):
            if not name:
                return False
            try:
                import serial.tools.list_ports as _lp
                return any(p.device == name for p in _lp.comports())
            except Exception:
                return True          # dans le doute on ne casse rien

        def _oumse_reconnect(self):
            """Ferme et rouvre sur le port MediaTek present. True si reussi."""
            old = getattr(self, "portname", None)
            sys.stderr.write("[oumse] port %s disparu, reconnexion...\n" % old)
            sys.stderr.flush()
            try:
                self.close()
            except Exception:
                pass
            self.connected = False
            deadline = time.time() + _RC_WAIT
            while time.time() < deadline:
                try:
                    found = self.detectdevices()
                except Exception:
                    found = []
                if found:
                    try:
                        self.portname = "DETECT"
                        if self.connect():
                            sys.stderr.write(
                                "[oumse] reconnecte sur %s\n"
                                % getattr(self, "portname", "?"))
                            sys.stderr.flush()
                            return True
                    except Exception as e:
                        sys.stderr.write("[oumse] reconnexion KO: %s\n"
                                         % str(e)[:80])
                        sys.stderr.flush()
                time.sleep(0.25)
            sys.stderr.write("[oumse] aucun port MediaTek revenu apres %.0fs\n"
                             % _RC_WAIT)
            sys.stderr.flush()
            return False

        _orig_usbread = _SC.usbread

        def _patched_usbread(self, *args, **kwargs):
            try:
                data = _orig_usbread(self, *args, **kwargs)
            except Exception:
                data = b""
            if data:
                self._oumse_empty = 0
                return data
            # lecture vide : normal en polling, suspect si ca dure
            n = getattr(self, "_oumse_empty", 0) + 1
            self._oumse_empty = n
            if n < 3 or getattr(self, "_oumse_reco", False):
                return data
            if _port_present(getattr(self, "portname", None)):
                return data          # le port existe toujours : rien a faire
            self._oumse_reco = True
            try:
                if _oumse_reconnect(self):
                    self._oumse_empty = 0
                    try:
                        return _orig_usbread(self, *args, **kwargs)
                    except Exception:
                        return b""
            finally:
                self._oumse_reco = False
            return data

        _SC.usbread = _patched_usbread
        sys.stderr.write("[oumse] seriallib reconnexion active (attente %.0fs)\n"
                         % _RC_WAIT)
        sys.stderr.flush()
    except Exception as _e:
        sys.stderr.write("[oumse] patch seriallib impossible: "
                         + str(_e)[:100] + "\n")
        sys.stderr.flush()


# ============================================================================
# LECTURE SERIE : ne pas conclure "rien" avant que le DA ait eu le temps
# ============================================================================
# seriallib.usbread() fait, quand on ne lui donne pas de longueur :
#       resplen = self.device.in_waiting
#       while bytestoread: ...
# Si rien n'est ENCORE arrive, in_waiting vaut 0, la boucle ne tourne pas et
# la fonction rend b"" immediatement. C'est exactement le cas juste apres le
# saut du DA : le DA met quelques centaines de ms a demarrer avant d'envoyer
# son CMD:START. mtkclient lit trop tot, ne voit rien, et abandonne.
# On attend donc qu'au moins un octet soit dispo avant de mesurer.
#
#   OUMSE_READ_WAIT=N  -> secondes d'attente max (defaut 3, 0 = desactive)
try:
    _READ_WAIT = max(0.0, float(os.environ.get("OUMSE_READ_WAIT", "3")))
except Exception:
    _READ_WAIT = 3.0

if _READ_WAIT > 0:
    try:
        from mtkclient.Library.Connection.seriallib import SerialClass as _SC2
        _prev_usbread = _SC2.usbread

        # v2 : on ne se contente plus d'attendre, on REFUSE d'appeler la
        # lecture bloquante quand le tampon est vide.
        #
        # Pourquoi : seriallib fait "self.device.timeout = 0.02" avant de lire.
        # Ce setter pyserial appelle _reconfigure_port(), qui ECHOUE une fois le
        # DA parti (erreur Windows 31) - et notre rustine avale l'erreur. Bilan :
        # la valeur 0.02 n'est jamais appliquee au port, qui garde le timeout
        # d'origine de connect() : serial.Serial(..., timeout=500). Chaque
        # lecture peut donc bloquer 500 SECONDES. C'est exactement le silence
        # qu'on observe apres "Jumping to 0x200000".
        #
        # On regarde donc in_waiting nous-memes et on rend b"" s'il n'y a rien,
        # sans jamais dependre du timeout du port.
        _GUARD_MAX = 0x10000          # au-dela = gros transfert, on ne touche pas

        def _waiting_usbread(self, resplen=None, maxtimeout=0, timeout=0,
                             w_max_packet_size=None):
            dev = getattr(self, "device", None)
            if dev is None:
                return _prev_usbread(self, resplen, maxtimeout, timeout,
                                     w_max_packet_size)
            want = 1 if resplen is None else max(1, int(resplen))
            if want > _GUARD_MAX:
                return _prev_usbread(self, resplen, maxtimeout, timeout,
                                     w_max_packet_size)
            end = time.time() + _READ_WAIT
            avail = 0
            while True:
                try:
                    avail = dev.in_waiting
                except Exception:
                    avail = 0
                    break
                if avail >= want or time.time() >= end:
                    break
                time.sleep(0.02)
            if avail <= 0:
                return b""            # tampon vide : on ne bloque PAS
            if resplen is None:
                return _prev_usbread(self, None, maxtimeout, timeout,
                                     w_max_packet_size)
            # on ne demande jamais plus que ce qui est deja arrive
            return _prev_usbread(self, min(want, avail), maxtimeout, timeout,
                                 w_max_packet_size)

        _SC2.usbread = _waiting_usbread
        sys.stderr.write("[oumse] lecture serie patiente active (%.1fs)\n"
                         % _READ_WAIT)
        sys.stderr.flush()
    except Exception as _e:
        sys.stderr.write("[oumse] patch lecture impossible: "
                         + str(_e)[:100] + "\n")
        sys.stderr.flush()


# ============================================================================
# JUMP_DA : le preloader V6 n'echo pas l'adresse
# ============================================================================
# Trace DEBUG du 18/09, mot pour mot :
#     TX:d5              (commande JUMP_DA)
#     RX:d5              (echo de la commande : OK)
#     TX:00200000        (adresse de saut)
#     <plus rien>
#
# mtk_preloader.jump_da() attend ensuite que le preloader lui RENVOIE
# l'adresse (rdword), puis un status. Ce preloader-la ne renvoie rien : il
# a deja saute. Le port COM reste present (verifie au moniteur), donc le
# telephone est bien vivant - c'est le DA qui tourne.
#
# En prime, la branche d'echec de jump_da() a un bug : elle utilise la
# variable 'status' qui n'a jamais ete affectee quand l'adresse n'est pas
# echoee -> UnboundLocalError au lieu d'un message clair.
#
# On remplace donc jump_da par une version qui :
#   1. laisse une vraie chance a l'echo (plusieurs essais sur N secondes) ;
#   2. si l'echo ne vient pas, considere le saut comme effectue et rend la
#      main au DA (c'est ce que font les outils qui marchent sur ce modele) ;
#   3. ne plante plus sur 'status'.
#
#   OUMSE_JUMP_OPTIMISTIC=0 -> comportement mtkclient d'origine
#   OUMSE_JUMP_WAIT=N       -> secondes d'attente de l'echo (defaut 3)
_JUMP_OPT = os.environ.get("OUMSE_JUMP_OPTIMISTIC", "1") != "0"
try:
    _JUMP_WAIT = max(0.5, float(os.environ.get("OUMSE_JUMP_WAIT", "3")))
except Exception:
    _JUMP_WAIT = 3.0

if _JUMP_OPT:
    try:
        from struct import pack as _pack
        from mtkclient.Library.mtk_preloader import Preloader as _PL

        def _patched_jump_da(self, addr):
            self.info("Jumping to %s" % hex(addr))
            try:
                self.config.set_gui_status(self.config.tr(
                    "Jumping to %s" % hex(addr)))
            except Exception:
                pass
            if not self.echo(self.Cmd.JUMP_DA.value):
                self.error("Jump_DA: la commande n'a pas ete acquittee.")
                return False
            self.usbwrite(_pack(">I", addr))

            # 1) on laisse au preloader le temps d'echoer l'adresse
            resaddr = None
            deadline = time.time() + _JUMP_WAIT
            while time.time() < deadline:
                try:
                    resaddr = self.rdword()
                except Exception:
                    resaddr = None
                if resaddr is not None:
                    break
                time.sleep(0.05)

            # 2) cas normal : l'adresse revient, on lit le status
            if resaddr == addr:
                status = None
                try:
                    status = self.rword()
                except Exception:
                    pass
                time.sleep(0.1)
                if status == 0:
                    self.info("Jumping to %s: ok." % hex(addr))
                    return True
                if status is None:
                    sys.stderr.write(
                        "[oumse] adresse echoee mais pas de status -> on "
                        "continue quand meme\n")
                    sys.stderr.flush()
                    return True
                self.error("Jump_DA status error: %s" % status)
                return False

            # 3) aucun echo : preloader V6 qui saute immediatement
            if resaddr is None:
                sys.stderr.write(
                    "[oumse] pas d'echo d'adresse apres JUMP_DA (%.1fs) -> "
                    "saut considere comme effectue, on passe la main au DA\n"
                    % _JUMP_WAIT)
                sys.stderr.flush()
                time.sleep(0.5)
                return True

            self.error("Jump_DA: adresse inattendue %s au lieu de %s"
                       % (hex(resaddr), hex(addr)))
            return False

        _PL.jump_da = _patched_jump_da
        sys.stderr.write("[oumse] jump_da tolerant actif (attente echo %.1fs)\n"
                         % _JUMP_WAIT)
        sys.stderr.flush()
    except Exception as _e:
        sys.stderr.write("[oumse] patch jump_da impossible: "
                         + str(_e)[:100] + "\n")
        sys.stderr.flush()


# ============================================================================
# ECRITURE SERIE : flush() ne doit JAMAIS bloquer
# ============================================================================
# Trace DEBUG du 18/09 (v6) : apres "Jumping to 0x200000" la sequence est
#     TX:00200000        (l'adresse est ECRITE - donc write() a rendu la main)
#     <plus rien>        (aucune lecture rdword derriere)
#
# seriallib.usbwrite() fait :  self.write(data) ; self.device.flush()
# self.write() loggue "TX:..." PUIS usbwrite appelle flush(). Comme il n'y a
# aucune trace de lecture ensuite, c'est flush() qui bloque : sur Windows
# pyserial.flush() = FlushFileBuffers(), qui attend que TOUT le tampon de
# sortie soit transmis. Une fois le DA parti, le peripherique ne draine plus
# le tampon -> flush attend jusqu'au timeout (500 s) = le silence observe.
#
# Pour un VCOM USB, l'ecriture atteint deja le peripherique ; flush n'est
# qu'une garantie "tout est parti". On le rend best-effort : execute dans un
# thread, borne a OUMSE_FLUSH_WAIT secondes, jamais bloquant.
#
#   OUMSE_FLUSH_GUARD=0   -> desactive (comportement d'origine)
#   OUMSE_FLUSH_WAIT=N    -> attente max du flush (defaut 1.0 s)
if os.environ.get("OUMSE_FLUSH_GUARD", "1") != "0":
    try:
        from mtkclient.Library.Connection.seriallib import SerialClass as _SCW
        try:
            _FLUSH_WAIT = max(0.05, float(os.environ.get("OUMSE_FLUSH_WAIT", "1")))
        except Exception:
            _FLUSH_WAIT = 1.0
        import threading as _thw

        def _bounded_flush(dev):
            if dev is None:
                return
            done = _thw.Event()

            def _do():
                try:
                    dev.flush()
                except Exception:
                    pass
                finally:
                    done.set()
            t = _thw.Thread(target=_do, daemon=True)
            t.start()
            if not done.wait(_FLUSH_WAIT):
                # flush toujours en cours : on ne l'attend pas, l'octet est
                # deja parti sur le fil. Le thread mourra avec le process.
                sys.stderr.write("[oumse] flush ignore (>%.1fs) apres ecriture\n"
                                 % _FLUSH_WAIT)
                sys.stderr.flush()

        _prev_usbwrite = _SCW.usbwrite

        def _patched_usbwrite(self, data, pktsize=None):
            if pktsize is None:
                pktsize = len(data)
            res = self.write(data, pktsize)
            _bounded_flush(getattr(self, "device", None))
            return res

        _SCW.usbwrite = _patched_usbwrite

        # usbreadwrite fait aussi un flush() nu au milieu -> meme traitement.
        _prev_urw = _SCW.usbreadwrite

        def _patched_usbreadwrite(self, data, resplen):
            self.usbwrite(data)
            _bounded_flush(getattr(self, "device", None))
            return self.usbread(resplen)

        _SCW.usbreadwrite = _patched_usbreadwrite
        sys.stderr.write("[oumse] flush serie borne a %.1fs (anti-blocage)\n"
                         % _FLUSH_WAIT)
        sys.stderr.flush()
    except Exception as _e:
        sys.stderr.write("[oumse] patch flush impossible: "
                         + str(_e)[:100] + "\n")
        sys.stderr.flush()


def emit(s):
    """Sortie immediate (flush) pour que le parent voit chaque ligne en temps reel."""
    print(s, flush=True)


# Traces techniques : visibles UNIQUEMENT si OUMSE_LAB_DEBUG=1 (banc d'essai).
# En production le client ne voit rien de plus qu'avant.
_DBG = os.environ.get("OUMSE_LAB_DEBUG", "") == "1"


def dbg(s):
    if _DBG:
        emit("OUMSE_DBG:" + s)


def resolve_loader(connect_mode):
    """Chemin du DA a utiliser : OUMSE_MTK_LOADER d'abord, sinon auto-detection."""
    loader_env = os.environ.get("OUMSE_MTK_LOADER", "").strip().strip('"')
    if loader_env:
        if os.path.isfile(loader_env):
            dbg("loader:env:" + loader_env)
            return loader_env
        dbg("loader:env_introuvable:" + loader_env)
    if connect_mode != "preloader":
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    for c in (os.path.join(here, "mtkclient", "Loader", "MTK_DA_V6.bin"),
              os.path.join(here, "mtkclient", "Loaders", "MTK_DA_V6.bin"),
              os.path.join(here, "mtkclient", "Loaders", "V6", "MTK_DA_V6.bin"),
              os.path.join(here, "Loader", "MTK_DA_V6.bin"),
              os.path.join(here, "Loaders", "MTK_DA_V6.bin")):
        if os.path.isfile(c):
            dbg("loader:auto:" + c)
            return c
    dbg("loader:aucun")
    return None


def resolve_auth():
    """Chemin du .auth : OUMSE_MTK_AUTH d'abord, sinon a cote du DA."""
    auth_env = os.environ.get("OUMSE_MTK_AUTH", "").strip().strip('"')
    if auth_env:
        if os.path.isfile(auth_env):
            dbg("auth:env:" + auth_env)
            return auth_env
        dbg("auth:env_introuvable:" + auth_env)
    here = os.path.dirname(os.path.abspath(__file__))
    for a in ("auth_sv5.auth", "MTK_DA_V6.auth", "auth.auth",
              "Transsion.auth", "km6.auth"):
        p = os.path.join(here, "mtkclient", "Loader", a)
        if os.path.isfile(p):
            dbg("auth:auto:" + p)
            return p
    dbg("auth:aucun")
    return None


def collect_partitions(mtk):
    """Renvoie [{name, size_bytes, sectors}] depuis la GPT chargee par configure_da."""
    out = []
    try:
        page_size = int(mtk.config.pagesize)
    except Exception:
        page_size = 512
    try:
        gpttable = mtk.daloader.get_partition_data(parttype="user")
    except Exception:
        gpttable = []
    if gpttable:
        for e in gpttable:
            name = getattr(e, "name", None)
            sectors = getattr(e, "sectors", None)
            if name and sectors:
                out.append({
                    "name": str(name),
                    "sectors": int(sectors),
                    "size": int(sectors) * page_size,
                })
    return out


def get_chip_name(mtk):
    try:
        cc = mtk.config.chipconfig
        if cc and getattr(cc, "name", None):
            return str(cc.name)
    except Exception:
        pass
    return "MediaTek"


def find_mtk_serial_port():
    """Cherche un port COM MediaTek MAINTENANT. Retourne le nom ou None.
    Sert juste a savoir si un driver VCOM serie est present sur la machine."""
    try:
        import serial.tools.list_ports
    except Exception:
        return None
    mtk_vids = (0x0E8D, 0x1004, 0x22D9, 0x0FCE)
    for port in serial.tools.list_ports.comports():
        vid = getattr(port, "vid", None)
        desc = (getattr(port, "description", "") or "").lower()
        if (vid in mtk_vids) or ("preloader" in desc) or ("vcom" in desc) \
                or ("mediatek" in desc):
            return port.device
    return None


def serial_support_available():
    """True si pyserial est installe (pour pouvoir utiliser le mode VCOM serie)."""
    try:
        import serial.tools.list_ports  # noqa
        return True
    except Exception:
        return False


def main():
    # OUMSE_LOG_DEBUG=1 : journal technique complet de mtkclient. Chaque lecture
    # et chaque ecriture serie/USB est tracee ("SERIAL usbread: length(...)"),
    # ce qui montre EXACTEMENT sur quel appel ca se bloque apres le saut du DA.
    # Reserve au banc d'essai : en production on reste en INFO.
    loglevel = logging.DEBUG if os.environ.get("OUMSE_LOG_DEBUG") == "1" \
        else logging.INFO
    if loglevel == logging.DEBUG:
        try:
            logging.basicConfig(level=logging.DEBUG, stream=sys.stderr,
                                format="%(name)s %(levelname)s %(message)s")
        except Exception:
            pass
        dbg("loglevel:DEBUG")

    # --- Mode demande (BROM Kamakiri V5 ou Preloader V6) ---
    # Lu AVANT le choix du transport car le transport en depend.
    connect_mode = (os.environ.get("OUMSE_BROM_MODE", "") or "").strip().lower()

    # ----- Choix du transport -----
    # Regle critique tiree de l'historique de reussite (cf transcript 10/06) :
    #
    #   * BROM mode (Kamakiri V5, chips type MT6768/KN4) :
    #     mtkclient DOIT etre laisse en mode auto (libusb -> fallback serial),
    #     PAS en "DETECT". Le mode "DETECT" forcait un timing USB different qui
    #     CASSAIT l'exploit Kamakiri. Avec serialportname=None, mtkclient choisit
    #     son transport (libusb si UsbDk dispo, sinon serial auto) et c'est
    #     ce comportement qui a permis le succes du 10 juin (Kamakiri OK + DA
    #     V5 auto-detecte + read/write proinfo OK).
    #
    #   * Preloader mode (V6, chips type MT6789/KM6) :
    #     le VCOM preloader expose un port COM tres brievement. mtkclient doit
    #     boucler en attendant -> on passe serialportname="DETECT" comme TFM.
    use_serial = serial_support_available()
    # v2 : override possible pour tester les deux transports sans reediter ce
    # fichier. OUMSE_BROM_TRANSPORT = auto | serial | COM7
    _tr = (os.environ.get("OUMSE_BROM_TRANSPORT", "") or "").strip().lower()
    if _tr in ("auto", "libusb", "usb"):
        serial_arg = None
        transport_label = "auto(libusb->serial fallback) [force]"
    elif _tr in ("serial", "detect", "vcom"):
        serial_arg = "DETECT"
        transport_label = "serial(DETECT) [force]"
    elif _tr.startswith("com"):
        serial_arg = _tr.upper()
        transport_label = "serial(%s) [force]" % _tr.upper()
    elif connect_mode == "preloader" and use_serial:
        serial_arg = "DETECT"
        transport_label = "serial(DETECT)"
    else:
        # BROM (defaut) ou pyserial non dispo -> mtkclient en mode auto
        serial_arg = None
        transport_label = "auto(libusb->serial fallback)"
    dbg("mode:" + (connect_mode or "brom"))
    dbg("transport:" + transport_label)

    # ----- Setup identique a mtk.py run() -----
    config = MtkConfig(loglevel=loglevel, gui=None, guiprogress=None)
    ArgHandler(argparse.Namespace(), config)

    # ========================================================================
    # CORRECTIF v2 - L'ORDRE COMPTE.
    # Mtk(...) construit son DAloader/DAconfig, qui RECOPIE config.loader et
    # config.auth a ce moment-la. Les affecter APRES la construction (comme le
    # faisait la v1, plus bas) n'avait donc aucun effet : le DA choisi par
    # l'utilisateur etait ignore et mtkclient reprenait MTK_DA_V6.bin.
    # mtk.py fait pareil : ArgHandler(args, config) AVANT Mtk(...).
    # ========================================================================
    chosen_loader = resolve_loader(connect_mode)
    chosen_auth = resolve_auth()
    if chosen_loader:
        try:
            config.loader = chosen_loader
        except Exception as e:
            emit("OUMSE_WARN:loader:" + str(e)[:80])
    if chosen_auth:
        try:
            config.auth = chosen_auth
        except Exception:
            pass

    mtk = Mtk(config=config, loglevel=loglevel, serialportname=serial_arg)
    # NOTE : on n'emet PLUS OUMSE_INFO:mode et OUMSE_INFO:transport - ces infos
    # exposent la logique technique interne (libusb/serial fallback, brom/preloader).
    # Le UI ne les afficherait pas de toute facon (filtre par _OUMSE_INFO_LABELS).
    config.set_peek(mtk.daloader.peek)
    mtk.config.preloader_filename = None

    # --- Loader DA : auto-detection selon le mode demande ---
    #   mode "preloader" (V6 chips a BROM patche) : on AUTO-CHARGE le MTK_DA_V6.bin
    #     trouve dans mtkclient/Loader/ ou mtkclient/Loaders/ ou Loaders/V6/.
    #   mode "brom" (Kamakiri, chips V5) : PAS de loader force, mtkclient
    #     auto-detecte MTK_DA_V5.bin (c'est ce qui marchait le 10 juin).
    #   Override possible via OUMSE_MTK_LOADER = chemin explicite.
    # --- Re-affirmation apres construction (ceinture ET bretelles) ---
    # Selon la version de mtkclient, daconfig peut relire config.loader plus
    # tard. On repose donc les memes valeurs sur l'objet construit : inoffensif
    # si deja pris en compte, utile sinon.
    if chosen_loader:
        try:
            mtk.config.loader = chosen_loader
            if getattr(mtk, "daloader", None) is not None:
                dac = getattr(mtk.daloader, "daconfig", None)
                if dac is not None and hasattr(dac, "loader"):
                    dac.loader = chosen_loader
                    dbg("daconfig.loader force")
        except Exception as e:
            emit("OUMSE_WARN:loader:" + str(e)[:80])
    if chosen_auth:
        try:
            mtk.config.auth = chosen_auth
        except Exception:
            pass
    # Verification : ce qui sera REELLEMENT envoye au telephone.
    try:
        _eff = getattr(mtk.config, "loader", None)
        dbg("loader_effectif:" + str(_eff))
        if chosen_loader and _eff and os.path.normcase(str(_eff)) != \
                os.path.normcase(chosen_loader):
            emit("OUMSE_WARN:loader_ignore:" + os.path.basename(str(_eff)))
    except Exception:
        pass

    da_handler = DaHandler(mtk, loglevel)

    # ----- Connexion (BROM -> exploit -> DA) -----
    emit("OUMSE_STEP:connect")
    # WATCHDOG : connect() peut boucler indefiniment sur "could not open port"
    # quand le COM est verrouille par un autre process (echec preloader laisse
    # le port locke). On limite a 60s : au-dela on abandonne proprement.
    import threading as _th
    _connect_result = {"mtk": None, "err": None}
    def _do_connect():
        try:
            _connect_result["mtk"] = da_handler.connect(mtk, ".")
        except Exception as e:
            _connect_result["err"] = str(e)[:120]
    _t = _th.Thread(target=_do_connect, daemon=True)
    _t.start()
    _t.join(timeout=60.0)
    if _t.is_alive():
        emit("OUMSE_FAIL:connect:timeout:port_locked_60s"); sys.exit(1)
    if _connect_result["err"]:
        emit("OUMSE_FAIL:connect:usb:" + _connect_result["err"]); sys.exit(1)
    mtk = _connect_result["mtk"]
    if mtk is None:
        emit("OUMSE_FAIL:connect:no_device"); sys.exit(1)
    try:
        mtk = da_handler.configure_da(mtk)
    except Exception as e:
        emit("OUMSE_FAIL:configure:" + str(e)[:80]); sys.exit(1)
    if mtk is None:
        emit("OUMSE_FAIL:configure:none"); sys.exit(1)

    # ----- Inventaire partitions + chip -----
    chip = get_chip_name(mtk)
    parts = collect_partitions(mtk)
    if not parts:
        emit("OUMSE_FAIL:gpt:empty"); sys.exit(1)

    # ----- Infos device neutres pour le UI (parse via OUMSE_INFO:<key>:<value>) -----
    # On expose UNIQUEMENT des infos publiques (code materiel, chipset, stockage,
    # nombre de partitions). Rien sur mtkclient, kamakiri, libusb, DA, exploit.
    try:
        hwcode = getattr(mtk.config, "hwcode", None)
        if hwcode:
            emit("OUMSE_INFO:hwcode:0x%X" % int(hwcode))
    except Exception:
        pass
    try:
        if chip and chip != "MediaTek":
            emit("OUMSE_INFO:soc:" + chip)
    except Exception:
        pass
    try:
        daconfig = getattr(mtk.daloader, "daconfig", None) if hasattr(mtk, "daloader") else None
        if daconfig and hasattr(daconfig, "flashtype"):
            ft = int(daconfig.flashtype or 0)
            storage_name = {1: "eMMC", 2: "NAND", 3: "UFS", 4: "SDcard", 0: "Auto"}.get(ft, "type %d" % ft)
            emit("OUMSE_INFO:storage:" + storage_name)
    except Exception:
        pass
    try:
        emit("OUMSE_INFO:partitions:" + str(len(parts)))
    except Exception:
        pass

    emit("OUMSE_READY:" + json.dumps(
        {"chip": chip, "partitions": parts}, ensure_ascii=False))

    # ----- Boucle de commandes (stdin -> ops -> stdout) -----
    while True:
        try:
            line = sys.stdin.readline()
        except Exception:
            break
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            cmd = json.loads(line)
        except Exception as e:
            emit("OUMSE_FAIL:bad_json:" + str(e)[:60])
            continue

        op = cmd.get("op")

        if op == "quit":
            emit("OUMSE_OK:quit")
            break

        if op == "reboot":
            emit("OUMSE_STEP:reboot")
            try:
                mtk.daloader.shutdown(bootmode=0)
                emit("OUMSE_OK:reboot")
            except Exception as e:
                emit("OUMSE_FAIL:reboot:" + str(e)[:80])
            break

        if op == "read":
            part = cmd.get("part", "")
            outp = cmd.get("out", "")
            if not part or not outp:
                emit("OUMSE_FAIL:read:missing_args"); continue
            emit("OUMSE_STEP:read:" + part)
            try:
                data = da_handler.da_read_partition(part)
                if not data:
                    emit("OUMSE_FAIL:read:" + part + ":empty"); continue
                try:
                    os.makedirs(os.path.dirname(outp) or ".", exist_ok=True)
                except Exception:
                    pass
                with open(outp, "wb") as f:
                    f.write(data)
                emit("OUMSE_OK:read:" + part + ":" + str(len(data)))
            except Exception as e:
                emit("OUMSE_FAIL:read:" + part + ":" + str(e)[:120])
            continue

        if op == "write":
            part = cmd.get("part", "")
            inp = cmd.get("in", "")
            if not part or not inp or not os.path.isfile(inp):
                emit("OUMSE_FAIL:write:missing_args"); continue
            emit("OUMSE_STEP:write:" + part)
            try:
                with open(inp, "rb") as f:
                    data = f.read()
                if not data:
                    emit("OUMSE_FAIL:write:" + part + ":empty_file"); continue
                res = da_handler.da_write_partition(part, data)
                if res:
                    emit("OUMSE_OK:write:" + part + ":" + str(len(data)))
                else:
                    emit("OUMSE_FAIL:write:" + part + ":refused")
            except Exception as e:
                emit("OUMSE_FAIL:write:" + part + ":" + str(e)[:120])
            continue

        if op == "erase":
            plist = cmd.get("parts") or []
            if isinstance(plist, str):
                plist = [plist]
            if not plist:
                emit("OUMSE_FAIL:erase:no_parts"); continue
            emit("OUMSE_STEP:erase:" + ",".join(plist))
            try:
                da_handler.da_erase(list(plist), "user")
                emit("OUMSE_OK:erase:" + ",".join(plist))
            except Exception as e:
                emit("OUMSE_FAIL:erase:" + str(e)[:120])
            continue

        emit("OUMSE_FAIL:unknown_op:" + str(op))

    sys.exit(0)


if __name__ == "__main__":
    main()
