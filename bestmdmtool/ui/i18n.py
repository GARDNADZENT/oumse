"""Interface translations for the BestMDMTool window shell.

Only the shell talks through this module: navigation labels, operation buttons,
header and footer text. Page internals stay in English so the tooling stays
readable, and any missing translation falls back to English instead of showing
a blank button.
"""

from __future__ import annotations

LANGUAGES = ("en", "fr", "pt", "ar")
LANGUAGE_LABELS = {"en": "EN", "fr": "FR", "pt": "PT", "ar": "AR"}
LANGUAGE_NAMES = {
    "en": "English",
    "fr": "Français",
    "pt": "Português",
    "ar": "العربية",
}
DEFAULT_LANGUAGE = "en"
RTL_LANGUAGES = ("ar",)


def normalize(language: str | None) -> str:
    """Return a supported language code, falling back to English."""

    code = (language or "").strip().lower().replace("_", "-")
    if code in LANGUAGES:
        return code
    base = code.split("-")[0]
    return base if base in LANGUAGES else DEFAULT_LANGUAGE


def is_rtl(language: str | None) -> bool:
    return normalize(language) in RTL_LANGUAGES


STRINGS: dict[str, dict[str, str]] = {
    # -- chrome ------------------------------------------------------------
    "app.session": {
        "en": "Local session",
        "fr": "Session locale",
        "pt": "Sessão local",
        "ar": "جلسة محلية",
    },
    "app.unlimited": {
        "en": "NO LOGIN",
        "fr": "SANS CONNEXION",
        "pt": "SEM LOGIN",
        "ar": "بدون تسجيل",
    },
    "app.engine": {"en": "Engine", "fr": "Moteur", "pt": "Motor", "ar": "المحرك"},
    "app.chip": {"en": "Chip", "fr": "Puce", "pt": "Chip", "ar": "الشريحة"},
    "app.uptime": {"en": "Uptime", "fr": "Durée", "pt": "Duração", "ar": "مدة الجلسة"},
    "app.language": {"en": "Language", "fr": "Langue", "pt": "Idioma", "ar": "اللغة"},
    "app.connect": {"en": "Connect", "fr": "Connecter", "pt": "Conectar", "ar": "اتصال"},
    "app.disconnect": {
        "en": "Disconnect",
        "fr": "Déconnecter",
        "pt": "Desconectar",
        "ar": "قطع الاتصال",
    },
    "app.no_session": {
        "en": "No session",
        "fr": "Aucune session",
        "pt": "Sem sessão",
        "ar": "لا توجد جلسة",
    },
    "app.session_open": {
        "en": "Session open",
        "fr": "Session ouverte",
        "pt": "Sessão aberta",
        "ar": "الجلسة مفتوحة",
    },
    "app.no_device": {"en": "No device", "fr": "Aucun appareil", "pt": "Sem aparelho", "ar": "لا جهاز"},
    "app.ready": {"en": "Ready", "fr": "Prêt", "pt": "Pronto", "ar": "جاهز"},
    "app.stop": {"en": "STOP", "fr": "STOP", "pt": "PARAR", "ar": "إيقاف"},
    "app.select_all": {
        "en": "Select all",
        "fr": "Tout cocher",
        "pt": "Marcar tudo",
        "ar": "تحديد الكل",
    },
    "app.select_none": {
        "en": "Unselect all",
        "fr": "Tout décocher",
        "pt": "Desmarcar tudo",
        "ar": "إلغاء التحديد",
    },
    "app.ops_mtk": {
        "en": "MTK OPERATIONS",
        "fr": "OPÉRATIONS MTK",
        "pt": "OPERAÇÕES MTK",
        "ar": "عمليات MTK",
    },
    "app.ops_spd": {
        "en": "SPD OPERATIONS",
        "fr": "OPÉRATIONS SPD",
        "pt": "OPERAÇÕES SPD",
        "ar": "عمليات SPD",
    },
    "app.ops_any": {
        "en": "OPERATIONS",
        "fr": "OPÉRATIONS",
        "pt": "OPERAÇÕES",
        "ar": "العمليات",
    },
    "app.group_device": {"en": "Device", "fr": "Appareil", "pt": "Aparelho", "ar": "الجهاز"},
    "app.group_reset": {
        "en": "Reset shortcuts",
        "fr": "Raccourcis reset",
        "pt": "Atalhos de reset",
        "ar": "اختصارات إعادة الضبط",
    },
    "app.group_diag": {"en": "Diagnostics", "fr": "Diagnostic", "pt": "Diagnóstico", "ar": "التشخيص"},
    "app.group_flash": {"en": "Flash", "fr": "Flash", "pt": "Flash", "ar": "التفليش"},
    "app.group_unlock": {
        "en": "Bootloader",
        "fr": "Bootloader",
        "pt": "Bootloader",
        "ar": "البوتلودر",
    },
    "app.tools": {"en": "TOOLS", "fr": "OUTILS", "pt": "FERRAMENTAS", "ar": "الأدوات"},
    "app.workspace": {
        "en": "WORKSPACE",
        "fr": "ESPACE DE TRAVAIL",
        "pt": "ÁREA DE TRABALHO",
        "ar": "مساحة العمل",
    },
    "app.log": {"en": "OUTPUT", "fr": "SORTIE", "pt": "SAÍDA", "ar": "الخرج"},
    "app.clear": {"en": "Clear", "fr": "Effacer", "pt": "Limpar", "ar": "مسح"},
    "app.save": {"en": "Save", "fr": "Enregistrer", "pt": "Salvar", "ar": "حفظ"},
    "app.ready_line": {
        "en": "Ready. Put the phone in BROM (MTK) or BSL (SPD) mode, then connect.",
        "fr": "Prêt. Mets le téléphone en mode BROM (MTK) ou BSL (SPD), puis connecte.",
        "pt": "Pronto. Coloque o aparelho em BROM (MTK) ou BSL (SPD) e conecte.",
        "ar": "جاهز. ضع الهاتف في وضع BROM أو BSL ثم اتصل.",
    },
    "app.connected_as": {
        "en": "%s · %s parts",
        "fr": "%s · %s partitions",
        "pt": "%s · %s partições",
        "ar": "%s · %s أقسام",
    },
    "app.no_tool": {
        "en": "This section has no extra actions.",
        "fr": "Cette section n'a pas d'action supplémentaire.",
        "pt": "Esta secção não tem ações extra.",
        "ar": "لا توجد إجراءات إضافية في هذا القسم.",
    },
    # -- navigation --------------------------------------------------------
    "nav.partitions": {
        "en": "Partition Manager MTK & SPD",
        "fr": "Gestionnaire de partitions MTK & SPD",
        "pt": "Gestor de partições MTK & SPD",
        "ar": "مدير الأقسام MTK و SPD",
    },
    "nav.mdm": {
        "en": "MDM Regional Patcher",
        "fr": "Patch régional MDM",
        "pt": "Patcher regional MDM",
        "ar": "رقع MDM الإقليمية",
    },
    "nav.brom": {
        "en": "Partition BROM mode",
        "fr": "Partition mode BROM",
        "pt": "Partição modo BROM",
        "ar": "الأقسام في وضع BROM",
    },
    "nav.bypass": {
        "en": "Direct Bypass MTK",
        "fr": "Contournement direct MTK",
        "pt": "Bypass direto MTK",
        "ar": "تجاوز مباشر MTK",
    },
    "nav.permanent": {
        "en": "Direct Permanent MTK",
        "fr": "Permanent direct MTK",
        "pt": "Permanente direto MTK",
        "ar": "دائم مباشر MTK",
    },
    "nav.tecno": {
        "en": "Tecno / Infinix Bootloader Unlock",
        "fr": "Déverrouillage Tecno / Infinix",
        "pt": "Desbloqueio Tecno / Infinix",
        "ar": "فتح بوتلودر Tecno / Infinix",
    },
    "nav.spd_unlock": {
        "en": "SPD / Unisoc Bootloader Unlock",
        "fr": "Déverrouillage SPD / Unisoc",
        "pt": "Desbloqueio SPD / Unisoc",
        "ar": "فتح بوتلودر SPD / Unisoc",
    },
    "nav.spd_parts": {
        "en": "Partition SPD / Unisoc & OF",
        "fr": "Partitions SPD / Unisoc & OF",
        "pt": "Partições SPD / Unisoc & OF",
        "ar": "أقسام SPD / Unisoc و OF",
    },
    "nav.spd_diag": {
        "en": "SPD Partition Diag Mode",
        "fr": "Mode Diag partitions SPD",
        "pt": "Modo Diag partições SPD",
        "ar": "وضع Diag لأقسام SPD",
    },
    "nav.rom": {
        "en": "Transsion ROM Maker",
        "fr": "Créateur de ROM Transsion",
        "pt": "Criador de ROM Transsion",
        "ar": "صانع ROM لـ Transsion",
    },
    "nav.spd_rom": {
        "en": "Transsion SPD ROM Maker",
        "fr": "Créateur ROM SPD Transsion",
        "pt": "Criador ROM SPD Transsion",
        "ar": "صانع ROM SPD لـ Transsion",
    },
    "nav.fastboot": {
        "en": "Fastboot OGT Flasher",
        "fr": "Flasheur Fastboot OGT",
        "pt": "Flasher Fastboot OGT",
        "ar": "مفليش Fastboot OGT",
    },
    "nav.dashboard": {"en": "Dashboard", "fr": "Tableau de bord", "pt": "Painel", "ar": "لوحة التحكم"},
    "nav.flasher": {
        "en": "Firmware Flasher",
        "fr": "Flasheur de firmware",
        "pt": "Flasher de firmware",
        "ar": "مفليش الفيرموير",
    },
    "nav.advanced": {
        "en": "Advanced Tools",
        "fr": "Outils avancés",
        "pt": "Ferramentas avançadas",
        "ar": "أدوات متقدمة",
    },
    "nav.chipsets": {
        "en": "Chipset Database",
        "fr": "Base de chipsets",
        "pt": "Base de chipsets",
        "ar": "قاعدة الشرائح",
    },
    "nav.settings": {"en": "Settings", "fr": "Paramètres", "pt": "Definições", "ar": "الإعدادات"},
    "nav.about": {"en": "About", "fr": "À propos", "pt": "Sobre", "ar": "حول"},
    # -- operations --------------------------------------------------------
    "op.partition_manager": {
        "en": "Partition Manager",
        "fr": "Gestionnaire de partitions",
        "pt": "Gestor de partições",
        "ar": "مدير الأقسام",
    },
    "op.read_info": {"en": "Read Info", "fr": "Lire les infos", "pt": "Ler informações", "ar": "قراءة المعلومات"},
    "op.enable_adb": {"en": "Enable ADB", "fr": "Activer ADB", "pt": "Ativar ADB", "ar": "تشغيل ADB"},
    "op.disable_adb": {"en": "Disable ADB", "fr": "Désactiver ADB", "pt": "Desativar ADB", "ar": "إيقاف ADB"},
    "op.reset_frp": {"en": "Reset FRP", "fr": "Réinitialiser FRP", "pt": "Repor FRP", "ar": "إعادة ضبط FRP"},
    "op.factory_reset": {
        "en": "Factory Reset",
        "fr": "Réinitialisation usine",
        "pt": "Reposição de fábrica",
        "ar": "إعادة ضبط المصنع",
    },
    "op.factory_frp": {
        "en": "Factory + FRP",
        "fr": "Usine + FRP",
        "pt": "Fábrica + FRP",
        "ar": "ضبط المصنع + FRP",
    },
    "op.refresh_table": {
        "en": "Refresh partition table",
        "fr": "Rafraîchir les partitions",
        "pt": "Atualizar tabela",
        "ar": "تحديث جدول الأقسام",
    },
    "op.read_selected": {
        "en": "Read selected",
        "fr": "Lire la sélection",
        "pt": "Ler seleção",
        "ar": "قراءة المحدد",
    },
    "op.write_selected": {
        "en": "Write selected",
        "fr": "Écrire la sélection",
        "pt": "Gravar seleção",
        "ar": "كتابة المحدد",
    },
    "op.erase_selected": {
        "en": "Erase selected",
        "fr": "Effacer la sélection",
        "pt": "Apagar seleção",
        "ar": "مسح المحدد",
    },
    "op.backup_all": {
        "en": "Back up all partitions",
        "fr": "Sauver toutes les partitions",
        "pt": "Backup de partições",
        "ar": "نسخ احتياطي لكل الأقسام",
    },
    "op.export_gpt": {
        "en": "Export partition table",
        "fr": "Exporter la table",
        "pt": "Exportar tabela",
        "ar": "تصدير جدول الأقسام",
    },
    "op.reboot": {"en": "Reboot device", "fr": "Redémarrer", "pt": "Reiniciar", "ar": "إعادة تشغيل"},
    "op.fastboot_devices": {
        "en": "Fastboot devices",
        "fr": "Appareils fastboot",
        "pt": "Aparelhos fastboot",
        "ar": "أجهزة fastboot",
    },
    "op.boot_state": {
        "en": "Bootloader state",
        "fr": "État du bootloader",
        "pt": "Estado do bootloader",
        "ar": "حالة البوتلودر",
    },
    "op.seccfg_unlock": {
        "en": "Unlock bootloader (seccfg)",
        "fr": "Déverrouiller (seccfg)",
        "pt": "Desbloquear (seccfg)",
        "ar": "فتح البوتلودر (seccfg)",
    },
    "op.seccfg_lock": {
        "en": "Lock bootloader (seccfg)",
        "fr": "Verrouiller (seccfg)",
        "pt": "Bloquear (seccfg)",
        "ar": "قفل البوتلودر (seccfg)",
    },
    "op.fastboot_unlock": {
        "en": "Fastboot flashing unlock",
        "fr": "Fastboot flashing unlock",
        "pt": "Fastboot flashing unlock",
        "ar": "Fastboot flashing unlock",
    },
    "op.open_pac": {
        "en": "Open PAC firmware",
        "fr": "Ouvrir un firmware PAC",
        "pt": "Abrir firmware PAC",
        "ar": "فتح فيرموير PAC",
    },
    "op.flash_pac": {
        "en": "Flash PAC firmware",
        "fr": "Flasher le PAC",
        "pt": "Flashear PAC",
        "ar": "تفليش PAC",
    },
    "op.extract_pac": {"en": "Extract PAC", "fr": "Extraire le PAC", "pt": "Extrair PAC", "ar": "استخراج PAC"},
    "op.build_pac": {
        "en": "Build PAC (ROM maker)",
        "fr": "Créer un PAC (ROM)",
        "pt": "Criar PAC (ROM)",
        "ar": "بناء PAC (روم)",
    },
    "op.diag_console": {
        "en": "DIAG console",
        "fr": "Console DIAG",
        "pt": "Consola DIAG",
        "ar": "طرفية DIAG",
    },
    "op.identify": {
        "en": "Identify phone (ATI)",
        "fr": "Identifier le téléphone (ATI)",
        "pt": "Identificar telefone (ATI)",
        "ar": "تعريف الهاتف (ATI)",
    },
    "op.doctor": {
        "en": "Connection doctor",
        "fr": "Diagnostic de connexion",
        "pt": "Diagnóstico da ligação",
        "ar": "فحص الاتصال",
    },
    "op.detect_usb": {
        "en": "Detect USB devices",
        "fr": "Détecter les appareils USB",
        "pt": "Detetar dispositivos USB",
        "ar": "كشف أجهزة USB",
    },
    "op.selftest": {
        "en": "Run backend self-test",
        "fr": "Auto-test du moteur",
        "pt": "Auto-teste do motor",
        "ar": "اختبار ذاتي للمحرك",
    },
    "op.save_settings": {
        "en": "Save settings",
        "fr": "Enregistrer les réglages",
        "pt": "Guardar definições",
        "ar": "حفظ الإعدادات",
    },
    "op.adb_shell": {"en": "ADB shell", "fr": "Shell ADB", "pt": "Shell ADB", "ar": "ADB shell"},
    "op.install_apk": {
        "en": "Install APK",
        "fr": "Installer un APK",
        "pt": "Instalar APK",
        "ar": "تثبيت APK",
    },
    "op.flash_raw": {
        "en": "Raw flash image",
        "fr": "Flash brut",
        "pt": "Flash bruto",
        "ar": "تفليش خام",
    },
    "op.flash_queue": {
        "en": "Flash the queue",
        "fr": "Flasher la file",
        "pt": "Flashear a fila",
        "ar": "تفليش القائمة",
    },
    "op.peek": {"en": "Memory peek", "fr": "Lire la mémoire", "pt": "Ler memória", "ar": "قراءة الذاكرة"},
    "op.poke": {"en": "Memory poke", "fr": "Écrire la mémoire", "pt": "Escrever memória", "ar": "كتابة الذاكرة"},
    "op.open_logs": {
        "en": "Open log folder",
        "fr": "Ouvrir les journaux",
        "pt": "Abrir registos",
        "ar": "فتح سجلات",
    },
    "op.support_bundle": {
        "en": "Export support bundle",
        "fr": "Exporter le diagnostic",
        "pt": "Exportar diagnóstico",
        "ar": "تصدير حزمة الدعم",
    },
    # -- notices -----------------------------------------------------------
    "notice.tag": {
        "en": "NOT INCLUDED",
        "fr": "NON INCLUS",
        "pt": "NÃO INCLUÍDO",
        "ar": "غير مضمّن",
    },
    "notice.title": {
        "en": "This action is not part of BestMDMTool",
        "fr": "Cette action ne fait pas partie de BestMDMTool",
        "pt": "Esta ação não faz parte do BestMDMTool",
        "ar": "هذا الإجراء ليس ضمن BestMDMTool",
    },
    "notice.policy": {
        "en": "BestMDMTool is an authorized-service tool. Lock and account bypass "
        "paths are left out on purpose, so nothing here can unlock a phone that "
        "is not yours. Everything else in the toolkit still works.",
        "fr": "BestMDMTool est un outil de service autorisé. Les contournements de "
        "verrouillage et de compte sont volontairement absents. Tout le reste "
        "de la boîte à outils fonctionne.",
        "pt": "O BestMDMTool é uma ferramenta de serviço autorizado. Os desvios de "
        "bloqueio e de conta ficam de fora de propósito. Todo o resto funciona.",
        "ar": "BestMDMTool أداة صيانة مصرّح بها. طرق تجاوز القفل والحساب مستبعدة "
        "بشكل مقصود، وبقية الأدوات تعمل كالمعتاد.",
    },
    "notice.mdm.body": {
        "en": "Regional MDM patching changes firmware to get past a device "
        "management enrolment. That is an MDM bypass, so it is not implemented.",
        "fr": "Le patch MDM régional modifie le firmware pour contourner un "
        "enrôlement de gestion. C'est un contournement MDM, donc absent.",
        "pt": "O patch MDM regional altera o firmware para contornar uma inscrição "
        "de gestão. É um bypass MDM, por isso não existe aqui.",
        "ar": "ترقيع MDM الإقليمي يعدّل الفيرموير لتجاوز إدارة الجهاز، وهو تجاوز "
        "مقصود استبعاده.",
    },
    "notice.bypass.body": {
        "en": "Direct bypass relies on patching partitions to skip the first-boot "
        "setup or an account check. That is a lock bypass and is not included.",
        "fr": "Le contournement direct modifie des partitions pour sauter la "
        "configuration initiale. C'est un contournement de verrou, non inclus.",
        "pt": "O bypass direto altera partições para saltar a configuração inicial. "
        "É um bypass de bloqueio e não está incluído.",
        "ar": "التجاوز المباشر يعتمد على ترقيع الأقسام لتخطي الإعداد الأول أو فحص "
        "الحساب، وهو تجاوز قفل غير مضمّن.",
    },
    "notice.permanent.body": {
        "en": "\"Permanent\" mode writes a patched boot chain so the bypass survives "
        "a reboot. It is the same lock bypass with a bigger blast radius, so it is "
        "not implemented either.",
        "fr": "Le mode « permanent » écrit une chaîne de démarrage modifiée pour "
        "survivre au redémarrage. C'est le même contournement, donc absent.",
        "pt": "O modo \"permanente\" grava uma cadeia de arranque alterada para "
        "sobreviver ao reinício. É o mesmo bypass, por isso não existe.",
        "ar": "الوضع الدائم يكتب سلسلة إقلاع معدّلة لتبقى بعد إعادة التشغيل، وهو "
        "نفس تجاوز القفل لذلك غير مضمّن.",
    },
    "notice.frp.body": {
        "en": "FRP is Google's factory-reset lock. Clearing it without the owner's "
        "account is an account bypass, so this button only explains itself.",
        "fr": "Le FRP est le verrou de réinitialisation de Google. Le lever sans le "
        "compte du propriétaire est un contournement de compte, donc ce bouton "
        "n'exécute rien.",
        "pt": "O FRP é o bloqueio de reposição da Google. Removê-lo sem a conta do "
        "proprietário é um bypass de conta, por isso este botão não executa nada.",
        "ar": "FRP هو قفل إعادة الضبط من Google. إزالته دون حساب المالك تعني تجاوز "
        "حساب، لذلك لا ينفّذ هذا الزر شيئًا.",
    },
    "notice.adb_disable.body": {
        "en": "Switching USB debugging off remotely needs a privileged helper app on "
        "the phone. Use the phone's developer options, or the ADB page for the "
        "commands that are supported.",
        "fr": "Désactiver le débogage USB à distance exige une application "
        "privilégiée sur le téléphone. Utilise les options développeur ou la page "
        "ADB pour les commandes prises en charge.",
        "pt": "Desligar a depuração USB remotamente exige uma app privilegiada no "
        "telefone. Usa as opções de programador ou a página ADB.",
        "ar": "إيقاف تصحيح USB عن بُعد يحتاج تطبيقًا مميّزًا على الهاتف. استخدم خيارات "
        "المطوّر أو صفحة ADB.",
    },
    "notice.open_instead": {
        "en": "Open %s instead",
        "fr": "Ouvrir %s à la place",
        "pt": "Abrir %s em vez disso",
        "ar": "افتح %s بدلًا من ذلك",
    },
}


def t(key: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Translate ``key``; unknown keys return themselves so mistakes are visible."""

    table = STRINGS.get(key)
    if not table:
        return key
    code = normalize(language)
    return table.get(code) or table.get(DEFAULT_LANGUAGE) or key
