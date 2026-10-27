# -*- coding: utf-8 -*-
"""
oumse_brom_runner.py - Runner MONO-SESSION pour le bypass MDM via BROM.
=======================================================================
v1.6 : refondu avec les protections du session_runner pour resoudre le crash
       0xC0000005 (STATUS_ACCESS_VIOLATION) qui survenait sur certains chipsets.
       Le code path mtkclient reste identique a la version precedente, mais on
       ajoute :
         - faulthandler          : dump du stack Python avant crash natif
         - connect watchdog       : timeout 90s sur le connect (evite boucle infinie)
         - sys.stdout.flush()     : apres chaque print (logs sauves avant crash)
         - GPT pre-check         : verifie que la partition existe avant le read
         - exceptions elargies   : capture BaseException (pas juste Exception)
         - print_exc auto        : trace complete dans stderr si Python catch

API EXTERNE INCHANGEE (compatible 100% avec oumse_brom.py cote tool) :
    Usage   : python oumse_brom_runner.py <partition> <patches.json|VERIFY>
    Sortie  : meme markers (OUMSE_STEP:, OUMSE_RESULT:, OUMSE_INFO:, OUMSE_READLEN:)
    Codes   : 0 = succes, 1 = echec
"""
import os
import sys
import json
import logging
import argparse
import time
import threading as _th
import traceback as _tb

# ============================================================================
# FAULTHANDLER : dump le stack Python si le process crashe (signal natif).
# ATTENTION : doit etre actif AVANT tout import lourd (libusb, mtkclient...).
# Sans ca, le code 0xC0000005 (ACCESS_VIOLATION) ne donne aucun indice sur OU
# l'erreur arrive.
# ============================================================================
import faulthandler
faulthandler.enable(file=sys.stderr)


# Force le flush sur chaque print pour ne pas perdre de log avant un crash natif.
def emit(line):
    """Print + flush immediat (resilient au crash : le log arrive AVANT le crash)."""
    try:
        print(line, flush=True)
    except Exception:
        try:
            sys.stdout.write(str(line) + "\n")
            sys.stdout.flush()
        except Exception:
            pass


# ============================================================================
# MONKEY-PATCH pyserial Windows (AVANT import mtkclient)
# ============================================================================
# Pendant l'upload DA stage 1 MTK, pyserial appelle SetCommState() ->
# Windows ERROR_GEN_FAILURE -> PermissionError(13) -> Error on sending DA.
try:
    import serial
    try:
        import serial.serialwin32 as _sw32
        _orig_reconfigure = _sw32.Serial._reconfigure_port
        def _patched_reconfigure(self, *args, **kwargs):
            last_err = None
            for attempt in range(5):
                try:
                    return _orig_reconfigure(self, *args, **kwargs)
                except (PermissionError, OSError) as e:
                    last_err = e
                    time.sleep(0.05 * (attempt + 1))
            try:
                sys.stderr.write(
                    "[oumse] _reconfigure_port swallow apres 5 retries: "
                    + str(last_err)[:120] + "\n")
                sys.stderr.flush()
            except Exception:
                pass
        _sw32.Serial._reconfigure_port = _patched_reconfigure
        sys.stderr.write("[oumse] pyserial _reconfigure_port patched\n")
        sys.stderr.flush()
    except Exception as _e:
        sys.stderr.write("[oumse] pyserial patch skip: " + str(_e)[:80] + "\n")
        sys.stderr.flush()
except ImportError:
    pass

# mtkclient doit etre importable : on tourne depuis son dossier (cwd = mtkclient).
try:
    from mtkclient.config.mtk_config import MtkConfig
    from mtkclient.Library.mtk_class import Mtk
    from mtkclient.Library.DA.mtk_da_handler import DaHandler
    from mtkclient.Library.mtk_main import ArgHandler
except Exception as e:
    emit("OUMSE_RESULT:FAIL:import mtkclient impossible: %s" % e)
    sys.exit(1)


def _fail(msg):
    emit("OUMSE_RESULT:FAIL:" + str(msg))
    sys.exit(1)


def _apply_patches(data, patches):
    """Applique single_offsets + fill_offsets (memes regles que le Direct META)."""
    buf = bytearray(data)
    n = len(buf)
    touched = 0
    for m in patches.get("single_offsets", []):
        off = int(m["offset"])
        val = int(m["value"]) & 0xFF
        if 0 <= off < n:
            buf[off] = val
            touched += 1
    for m in patches.get("fill_offsets", []):
        start = int(m["start"])
        end = int(m["end"])
        val = int(m["value"]) & 0xFF
        for i in range(start, min(end + 1, n)):
            buf[i] = val
            touched += 1
    return bytes(buf), touched


def _serial_support_available():
    try:
        import serial.tools.list_ports  # noqa
        return True
    except Exception:
        return False


def _gpt_has_partition(mtk, partname):
    """v1.6 : verifie que la partition existe dans la GPT chargee.
    Renvoie True/False/None (None = GPT non parseable -> laisser passer).
    Necessaire pour eviter un crash natif dans da_read_partition() quand la
    partition est introuvable et que mtkclient fait un acces memoire invalide."""
    try:
        daconfig = getattr(mtk.daloader, "daconfig", None)
        gpt = getattr(daconfig, "gpt", None) if daconfig else None
        entries = getattr(gpt, "partentries", None) if gpt else None
        if not entries:
            return None
        partname_lc = (partname or "").strip().lower()
        for e in entries:
            try:
                ename = getattr(e, "name", "") or ""
                if ename.strip().lower() == partname_lc:
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return None


def _connect_with_watchdog(da_handler, mtk, timeout=90):
    """v1.6 : appelle da_handler.connect() dans un thread avec timeout.
    Evite que le process boucle indefiniment si le device se deconnecte
    pendant le handshake BROM."""
    result = {"mtk": None, "err": None, "done": False}

    def _worker():
        try:
            result["mtk"] = da_handler.connect(mtk, ".")
        except BaseException as e:
            result["err"] = str(e)[:200]
            try:
                _tb.print_exc(file=sys.stderr)
            except Exception:
                pass
        finally:
            result["done"] = True

    t = _th.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if not result["done"]:
        return None, "connect timeout %ds (USB lock ?)" % timeout
    if result["err"]:
        return None, result["err"]
    return result["mtk"], None


def main():
    if len(sys.argv) < 3:
        _fail("usage: oumse_brom_runner.py <partition> <patches.json>")
    partition = sys.argv[1]
    patches_path = sys.argv[2]

    verify_mode = (patches_path.upper() == "VERIFY")
    patches = {}
    if not verify_mode:
        try:
            with open(patches_path, "r", encoding="utf-8") as f:
                patches = json.load(f)
        except Exception as e:
            _fail("patches.json illisible: %s" % e)

    loglevel = logging.INFO

    connect_mode = (os.environ.get("OUMSE_BROM_MODE", "") or "").strip().lower()

    if connect_mode == "preloader" and _serial_support_available():
        serial_arg = "DETECT"
    else:
        serial_arg = None

    config = MtkConfig(loglevel=loglevel, gui=None, guiprogress=None)
    ArgHandler(argparse.Namespace(), config)
    mtk = Mtk(config=config, loglevel=loglevel, serialportname=serial_arg)
    config.set_peek(mtk.daloader.peek)
    mtk.config.preloader_filename = None

    # --- Loader DA : auto-detection selon le mode ---
    loader_env = os.environ.get("OUMSE_MTK_LOADER", "").strip()
    chosen_loader = None
    if loader_env and os.path.isfile(loader_env):
        chosen_loader = loader_env
    elif connect_mode == "preloader":
        here = os.path.dirname(os.path.abspath(__file__))
        for c in (
            os.path.join(here, "mtkclient", "Loader", "MTK_DA_V6.bin"),
            os.path.join(here, "mtkclient", "Loaders", "MTK_DA_V6.bin"),
            os.path.join(here, "mtkclient", "Loaders", "V6", "MTK_DA_V6.bin"),
        ):
            if os.path.isfile(c):
                chosen_loader = c
                break
    if chosen_loader:
        try:
            mtk.config.loader = chosen_loader
        except Exception:
            pass

    da_handler = DaHandler(mtk, loglevel)

    # ----- Connexion BROM (v1.6 : avec watchdog 90s) -----
    mtk, err = _connect_with_watchdog(da_handler, mtk, timeout=90)
    if mtk is None:
        if err:
            _fail("connexion BROM echouee: " + err)
        _fail("connexion BROM echouee (telephone en BROM ? UsbDk installe ?)")

    # ----- v1.6 : auto-detection V6 selon hwcode APRES connect, AVANT configure_da -----
    # mtkclient ne charge pas toujours le bon DA pour les chipsets V6 recents
    # (MT6835/Dimensity 6100+, MT6789, MT6855, etc.) quand le mode "brom" est
    # demande. Resultat : "Failed to upload DA" sur MT6835 alors que le telephone
    # est bien en BROM physique. Solution : lire hwcode juste apres le connect,
    # et si c'est un chipset V6 connu, forcer MTK_DA_V6.bin avant configure_da.
    #
    # Liste des hwcodes V6 connus (a etendre au fur et a mesure des modeles testes) :
    V6_HWCODES = {
        0x989,   # MT6835 (Dimensity 6100+) - Tecno KM9, POVA Slim
        0x8127,  # MT6789 (variants Camon 50)
        0x886,   # MT6878 (Dimensity 7050)
        0x813,   # MT6855 (Dimensity 8050)
    }
    try:
        hwcode_val = int(getattr(mtk.config, "hwcode", 0) or 0)
    except Exception:
        hwcode_val = 0

    if hwcode_val in V6_HWCODES and not chosen_loader:
        # Force DA V6 pour les chipsets V6 detectes en BROM
        here = os.path.dirname(os.path.abspath(__file__))
        for c in (
            os.path.join(here, "mtkclient", "Loader", "MTK_DA_V6.bin"),
            os.path.join(here, "mtkclient", "Loaders", "MTK_DA_V6.bin"),
            os.path.join(here, "mtkclient", "Loaders", "V6", "MTK_DA_V6.bin"),
            os.path.join(here, "Loader", "MTK_DA_V6.bin"),
            os.path.join(here, "Loaders", "MTK_DA_V6.bin"),
        ):
            if os.path.isfile(c):
                try:
                    mtk.config.loader = c
                    emit("OUMSE_INFO:loader:V6 (auto, hwcode 0x%X)" % hwcode_val)
                except Exception:
                    pass
                break
        else:
            # Aucun DA V6 trouve - on previent mais on continue (mtkclient peut
            # avoir une logique interne pour ce chipset)
            sys.stderr.write(
                "[oumse] hwcode 0x%X est V6 mais MTK_DA_V6.bin introuvable\n"
                % hwcode_val)
            sys.stderr.flush()

    # ----- Configure DA (charge la GPT) -----
    try:
        mtk = da_handler.configure_da(mtk)
    except BaseException as e:
        try:
            _tb.print_exc(file=sys.stderr)
        except Exception:
            pass
        _fail("configure_da: " + str(e)[:200])
    if mtk is None:
        _fail("configuration DA echouee")

    # ----- Infos device (parse via OUMSE_INFO:<key>:<value>) -----
    try:
        hwcode = getattr(mtk.config, "hwcode", None)
        if hwcode:
            emit("OUMSE_INFO:hwcode:0x%X" % int(hwcode))
    except Exception:
        pass
    try:
        cc = getattr(mtk.config, "chipconfig", None)
        if cc and getattr(cc, "name", None):
            emit("OUMSE_INFO:soc:%s" % cc.name)
    except Exception:
        pass
    try:
        daconfig = getattr(mtk.daloader, "daconfig", None) if hasattr(mtk, "daloader") else None
        if daconfig and hasattr(daconfig, "flashtype"):
            ft = int(daconfig.flashtype or 0)
            storage_name = {1: "eMMC", 2: "NAND", 3: "UFS", 4: "SDcard", 0: "Auto"}.get(ft, "type %d" % ft)
            emit("OUMSE_INFO:storage:%s" % storage_name)
    except Exception:
        pass

    # ----- v1.6 : Verifie que la partition existe dans la GPT AVANT le read -----
    # Evite un crash natif dans da_read_partition() si la partition n'est pas
    # dans la table (lookup interne mtkclient peut faire un access invalide).
    exists = _gpt_has_partition(mtk, partition)
    if exists is False:
        _fail("partition '%s' introuvable dans la GPT" % partition)

    # ----- Lecture de la partition entiere en RAM -----
    emit("OUMSE_STEP:READ")
    try:
        data = da_handler.da_read_partition(partition)
    except BaseException as e:
        try:
            _tb.print_exc(file=sys.stderr)
        except Exception:
            pass
        _fail("lecture %s: %s" % (partition, str(e)[:200]))
    if not data:
        _fail("lecture %s vide" % partition)
    emit("OUMSE_READLEN:%d" % len(data))

    # ----- Patch MDM -----
    if verify_mode:
        patched = data
        emit("OUMSE_PATCHED:0 (mode VERIFY - reecriture identique)")
    else:
        patched, touched = _apply_patches(data, patches)
        emit("OUMSE_PATCHED:%d" % touched)
        if touched == 0:
            _fail("aucun offset applique (patches vides ou hors limites)")

    # ----- Reecriture de la partition entiere -----
    emit("OUMSE_STEP:WRITE")
    try:
        res = da_handler.da_write_partition(partition, patched)
    except BaseException as e:
        try:
            _tb.print_exc(file=sys.stderr)
        except Exception:
            pass
        _fail("ecriture %s: %s" % (partition, str(e)[:200]))
    if not res:
        _fail("ecriture %s refusee" % partition)

    # ----- Fin de l'operation : OK emis AVANT reboot pour survivre au crash USB -----
    # v1.6 : l'appel shutdown() envoie d'abord la commande reboot au telephone,
    # PUIS ferme le handle USB. C'est la fermeture USB qui crash en
    # ACCESS_VIOLATION sur certains chipsets (bug pyusb + libusb sur Windows).
    #
    # Strategie :
    #   1. emit OUMSE_RESULT:OK + flush  -> le tool lit le succes IMMEDIATEMENT
    #      depuis le buffer stdout (transmis a la pipe parent grace au flush).
    #   2. shutdown(bootmode=0)          -> envoie la commande REBOOT au telephone.
    #                                        Le telephone commence a redemarrer.
    #   3. Si shutdown crash en libusb : peu importe, OK est deja dans la pipe et
    #      le telephone a deja recu reboot. Le tool parse OK et ignore le code
    #      de sortie 0xC0000005.
    #   4. Si shutdown reussit : on fait os._exit(0) pour un exit OS-level propre.
    emit("OUMSE_RESULT:OK")
    sys.stdout.flush()
    sys.stderr.flush()

    try:
        mtk.daloader.shutdown(bootmode=0)
    except BaseException:
        # Le bug ACCESS_VIOLATION est dans libusb close_device (apres l'envoi
        # de la commande reboot). Le telephone a deja recu reboot, on s'en fout.
        pass

    # Exit OS-level (bypass Python finalizers qui peuvent re-crasher dans libusb).
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:
        # Filet de securite : si quelque chose remonte ici, on dump et on quitte
        # proprement avec un message lisible cote tool.
        try:
            _tb.print_exc(file=sys.stderr)
        except Exception:
            pass
        try:
            emit("OUMSE_RESULT:FAIL:exception non geree: " + str(e)[:200])
        except Exception:
            pass
        sys.exit(1)
