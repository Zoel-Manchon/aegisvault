"""Polished AegisVault desktop theme."""

from .design.tokens import (
    ACCENT,
    ACCENT_2,
    ACCENT_DIM,
    BG,
    BORDER,
    BORDER_SOFT,
    DANGER,
    ELEV,
    ELEV_2,
    GOOD,
    MUTED,
    MUTED_2,
    PANEL,
    PANEL_2,
    TEXT,
    WARNING,
)

STYLESHEET = f"""
* {{
    font-family: "Inter", "Segoe UI Variable", "Segoe UI", "SF Pro Display", Arial, sans-serif;
}}
QWidget {{
    background: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QLabel {{ background: transparent; }}
QWidget#detailContent, QWidget#featureGrid, QWidget#settingsPage {{ background: transparent; }}

/* Application shell ------------------------------------------------------ */
QWidget#appShell {{
    background: qradialgradient(cx:0.06, cy:0.00, radius:1.10,
        stop:0 rgba(37, 99, 235, 42), stop:0.36 #07101F, stop:0.74 #050814, stop:1 #03050B);
}}
QFrame#topbar, QFrame#sidebar, QFrame#listWrap, QFrame#detailPanel {{
    background: rgba(9, 15, 30, 232);
    border: 1px solid rgba(76, 92, 130, 82);
    border-radius: 18px;
}}
QFrame#topbar {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(12, 20, 39, 246), stop:0.55 rgba(8, 14, 28, 244), stop:1 rgba(7, 12, 24, 242));
    border: 1px solid rgba(88, 105, 148, 84);
}}
QFrame#sidebar {{
    background: rgba(7, 12, 25, 226);
}}
QFrame#listWrap {{
    background: rgba(9, 15, 31, 224);
}}
QFrame#detailPanel {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(13, 21, 41, 235), stop:1 rgba(7, 12, 26, 240));
}}
QScrollArea#detailScroll, QScrollArea#settingsScroll {{
    background: transparent;
    border: none;
}}
QFrame#sectionHeader {{
    background: transparent;
    border: none;
}}
QFrame#lineSeparator {{
    background: rgba(57, 72, 105, 120);
    max-height: 1px;
    border: none;
}}

/* Typography ------------------------------------------------------------- */
QLabel#brand {{ font-size: 23px; font-weight: 860; color: {TEXT}; letter-spacing: -0.72px; }}
QLabel#brandAccent {{ font-size: 23px; font-weight: 860; color: {ACCENT_2}; letter-spacing: -0.72px; }}
QLabel#tagline {{ color: {MUTED}; font-size: 10px; letter-spacing: 1.70px; font-weight: 700; }}
QLabel#h1 {{ font-size: 24px; font-weight: 820; color: {TEXT}; letter-spacing: -0.45px; }}
QLabel#h2 {{ font-size: 15px; font-weight: 760; color: {TEXT}; }}
QLabel#muted {{ color: {MUTED}; font-size: 13px; line-height: 1.35; }}
QLabel#smallMuted {{ color: {MUTED}; font-size: 11px; }}
QLabel#tinyMuted {{ color: {MUTED_2}; font-size: 10px; }}
QLabel#mono {{ color: {ACCENT_2}; font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace; font-size: 10px; letter-spacing: 1.15px; font-weight: 750; }}
QLabel#metricValue {{ color: {TEXT}; font-size: 24px; font-weight: 860; letter-spacing: -0.45px; }}
QLabel#code {{ font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace; font-size: 31px; font-weight: 820; color: {ACCENT_2}; letter-spacing: 4px; }}

/* Cards ------------------------------------------------------------------ */
QFrame#featureCard, QFrame#emptyCard, QFrame#detailCard, QFrame#healthCard, QFrame#metricCard, QFrame#metricTile {{
    background: rgba(13, 21, 42, 220);
    border: 1px solid rgba(70, 86, 126, 92);
    border-radius: 16px;
}}
QFrame#emptyCard {{
    background: rgba(10, 17, 34, 190);
}}
QFrame#detailCard {{
    background: rgba(12, 20, 39, 224);
    border: 1px solid rgba(77, 93, 136, 100);
}}
QFrame#metricTile {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(24, 34, 58, 232), stop:1 rgba(10, 17, 34, 234));
    border: 1px solid rgba(80, 97, 142, 105);
}}
QFrame#metricTile:hover, QFrame#metricCard:hover, QFrame#detailCard:hover {{
    border: 1px solid rgba(91, 108, 255, 135);
    background: rgba(17, 27, 52, 238);
}}
QFrame#entryCard {{
    background: rgba(11, 18, 36, 220);
    border: 1px solid rgba(52, 65, 98, 125);
    border-radius: 14px;
}}
QFrame#entryCard:hover {{
    background: rgba(17, 27, 52, 238);
    border: 1px solid rgba(91, 108, 255, 145);
}}
QFrame#entryCard[selected="true"] {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(36, 50, 95, 245), stop:1 rgba(12, 21, 43, 242));
    border: 1px solid rgba(34, 211, 238, 145);
}}
QFrame#healthCard {{
    background: rgba(8, 25, 30, 170);
    border: 1px solid rgba(52, 211, 153, 76);
}}

/* Badges ----------------------------------------------------------------- */
QLabel#badgeOn, QLabel#badgeOff, QLabel#badgeSoft, QLabel#ztPill {{
    border-radius: 13px;
    padding: 7px 12px;
    font-weight: 780;
    font-size: 11px;
}}
QLabel#badgeOn {{ background: rgba(52, 211, 153, 30); color: #A7F3D0; border: 1px solid rgba(52, 211, 153, 90); }}
QLabel#badgeSoft {{ background: rgba(34, 211, 238, 28); color: #A5F3FC; border: 1px solid rgba(34, 211, 238, 75); }}
QLabel#badgeOff {{ background: rgba(15, 23, 42, 135); color: {MUTED}; border: 1px solid {BORDER}; }}
QLabel#ztPill {{
    background: rgba(15, 23, 47, 184);
    border: 1px solid rgba(91, 104, 156, 105);
    color: #DDE6FF;
}}
QLabel#ztPill[tone="good"] {{ background: rgba(52, 211, 153, 30); border: 1px solid rgba(52, 211, 153, 90); color: #A7F3D0; }}
QLabel#ztPill[tone="warn"] {{ background: rgba(251, 191, 36, 28); border: 1px solid rgba(251, 191, 36, 86); color: #FDE68A; }}
QLabel#ztPill[tone="danger"] {{ background: rgba(251, 113, 133, 26); border: 1px solid rgba(251, 113, 133, 86); color: #FDA4AF; }}

/* Inputs ----------------------------------------------------------------- */
QLineEdit, QComboBox, QSpinBox {{
    background: rgba(6, 11, 23, 224);
    border: 1px solid rgba(60, 75, 112, 140);
    border-radius: 12px;
    padding: 10px 12px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    min-height: 22px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid rgba(34, 211, 238, 150);
    background: rgba(8, 14, 29, 245);
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    selection-background-color: {ACCENT};
    selection-color: white;
    outline: none;
    padding: 4px;
}}
QPlainTextEdit {{
    background: rgba(6, 11, 23, 224);
    border: 1px solid rgba(60, 75, 112, 140);
    border-radius: 12px;
    padding: 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QCheckBox {{ spacing: 10px; padding: 4px; color: {TEXT}; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid rgba(60, 75, 112, 150); background: rgba(8,11,29,230); }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; }}

/* Buttons ---------------------------------------------------------------- */
QPushButton {{
    background: rgba(14, 23, 44, 218);
    border: 1px solid rgba(70, 86, 126, 112);
    border-radius: 12px;
    padding: 10px 16px;
    color: {TEXT};
    font-weight: 690;
}}
QPushButton:hover {{
    border: 1px solid rgba(34, 211, 238, 135);
    background: rgba(20, 31, 57, 240);
}}
QPushButton:pressed {{ background: rgba(13, 22, 42, 255); }}
QPushButton:disabled {{ color: {MUTED_2}; background: rgba(12, 18, 32, 120); border: 1px solid rgba(52, 65, 98, 80); }}
QPushButton#primary {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #5B6CFF, stop:1 #2563EB);
    color: white;
    border: none;
    font-size: 14px;
}}
QPushButton#primary:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #7C86FF, stop:1 #3B82F6); }}
QPushButton#ghost {{ background: rgba(8, 14, 28, 110); border: 1px solid rgba(60, 75, 112, 125); }}
QPushButton#danger:hover {{ border: 1px solid {DANGER}; color: {DANGER}; }}
QPushButton#topNav, QPushButton#filterBtn, QPushButton#pageBtn {{
    background: rgba(7, 12, 25, 145);
    border: 1px solid rgba(65, 82, 121, 92);
}}
QPushButton#topNav:hover, QPushButton#filterBtn:hover, QPushButton#pageBtn:hover {{
    background: rgba(18, 27, 50, 230);
    border: 1px solid rgba(34, 211, 238, 115);
}}
QPushButton#topNav::menu-indicator {{ image: none; width: 0px; }}
QPushButton#topNavActive, QPushButton#pageActive {{
    background: rgba(91, 108, 255, 68);
    border: 1px solid rgba(91, 108, 255, 130);
}}
QPushButton#sideNav {{
    background: transparent;
    border: 1px solid transparent;
    color: #B9C2DD;
    text-align: left;
}}
QPushButton#sideNav:hover {{
    background: rgba(34, 211, 238, 18);
    border: 1px solid rgba(34, 211, 238, 60);
}}
QPushButton#sideActive {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(91, 108, 255, 92), stop:1 rgba(34, 211, 238, 20));
    border: 1px solid rgba(91, 108, 255, 118);
    color: white;
    text-align: left;
}}
QPushButton#categoryCard {{
    text-align: left;
    padding: 17px 18px;
    border-radius: 18px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(16, 27, 52, 235), stop:1 rgba(9, 15, 30, 235));
    border: 1px solid rgba(76, 92, 130, 105);
    color: {TEXT};
    font-size: 13px;
    font-weight: 760;
    line-height: 1.45;
}}
QPushButton#categoryCard:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(22, 34, 66, 245), stop:1 rgba(10, 19, 38, 245));
    border: 1px solid rgba(34, 211, 238, 125);
}}

/* Lists and tables ------------------------------------------------------- */
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border: none; margin: 0; padding: 0; }}
QListWidget::item:selected {{ background: transparent; }}
QTableWidget {{
    background: rgba(7, 12, 25, 210);
    border: 1px solid rgba(60, 75, 112, 128);
    border-radius: 12px;
    gridline-color: rgba(38,48,79,145);
    selection-background-color: rgba(91,108,255,80);
    selection-color: {TEXT};
}}
QHeaderView::section {{
    background: rgba(15, 23, 42, 235);
    color: {MUTED};
    border: none;
    border-right: 1px solid rgba(60, 75, 112, 110);
    border-bottom: 1px solid rgba(60, 75, 112, 110);
    padding: 8px;
    font-weight: 760;
}}

/* Progress/scroll/menu --------------------------------------------------- */
QProgressBar {{ background: rgba(5, 8, 18, 230); border: none; border-radius: 4px; max-height: 8px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACCENT}, stop:1 {ACCENT_2}); border-radius: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 5px 0; }}
QScrollBar::handle:vertical {{ background: rgba(91, 108, 255, 105); border-radius: 5px; min-height: 34px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(34, 211, 238, 150); }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: rgba(91, 108, 255, 105); border-radius: 4px; min-width: 34px; }}
QSplitter::handle {{ background: transparent; }}
QMenu {{ background: {PANEL_2}; border: 1px solid {BORDER}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 9px 22px 9px 16px; border-radius: 8px; color: {TEXT}; margin: 1px 2px; }}
QMenu::item:selected {{ background: rgba(91, 108, 255, 120); color: white; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 6px 8px; }}
QToolTip {{ background: {PANEL_2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px; }}

/* Dialogs ---------------------------------------------------------------- */
QDialog {{ background: qradialgradient(cx:0.20, cy:0.02, radius:1.10, stop:0 #101A35, stop:0.45 #0A1020, stop:1 #060A15); }}
QFrame#dialogHero {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(18, 31, 59, 242), stop:1 rgba(11, 19, 40, 236));
    border: 1px solid rgba(91, 108, 255, 90);
    border-radius: 18px;
}}
QFrame#settingsRow, QFrame#formCard, QFrame#policyCallout {{
    background: rgba(11, 19, 38, 224);
    border: 1px solid rgba(70, 86, 126, 102);
    border-radius: 16px;
}}
QFrame#settingsRow:hover, QFrame#formCard:hover {{
    border: 1px solid rgba(34, 211, 238, 115);
    background: rgba(14, 24, 47, 238);
}}
QFrame#policyCallout {{
    background: rgba(34, 211, 238, 20);
    border: 1px solid rgba(34, 211, 238, 70);
}}
QTabWidget#settingsTabs::pane {{
    background: rgba(8, 14, 29, 92);
    border: 1px solid rgba(68, 81, 132, 112);
    border-radius: 16px;
    top: -1px;
}}
QTabBar::tab {{
    background: rgba(8, 14, 29, 180);
    border: 1px solid rgba(68, 81, 132, 90);
    color: #B9C2DD;
    padding: 10px 18px;
    margin-right: 6px;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    font-weight: 720;
}}
QTabBar::tab:selected {{
    color: white;
    background: rgba(91, 108, 255, 78);
    border: 1px solid rgba(91, 108, 255, 140);
}}
QTabBar::tab:hover {{ border: 1px solid rgba(34, 211, 238, 110); }}


QDialog#startupSplash {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(18, 31, 59, 252), stop:1 rgba(6, 10, 21, 252));
    border: 1px solid rgba(91, 108, 255, 120);
    border-radius: 24px;
}}
QLabel#splashTitle {{
    color: white;
    font-size: 21px;
    font-weight: 850;
}}
QLabel#splashStatus, QLabel#unlockStatus {{
    color: #AEBAD6;
    font-size: 12px;
    font-weight: 650;
}}
QProgressBar#splashProgress, QProgressBar#unlockProgress {{
    background: rgba(4, 8, 18, 235);
    border: 1px solid rgba(56, 70, 110, 120);
    border-radius: 6px;
    min-height: 10px;
    max-height: 10px;
}}

/* Zero Trust command center ---------------------------------------------- */
QFrame#ztHero {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(21, 35, 67, 250), stop:0.54 rgba(11, 20, 41, 246), stop:1 rgba(6, 11, 24, 250));
    border: 1px solid rgba(34, 211, 238, 78);
    border-radius: 24px;
}}
QFrame#ztScoreCard {{
    background: rgba(5, 10, 22, 172);
    border: 1px solid rgba(34, 211, 238, 78);
    border-radius: 20px;
}}
QFrame#ztTrustStrip {{
    background: rgba(6, 11, 24, 112);
    border: 1px solid rgba(70, 86, 126, 72);
    border-radius: 16px;
}}
QLabel#ztTitle {{
    font-size: 30px;
    font-weight: 900;
    color: white;
    letter-spacing: -0.75px;
}}
QLabel#ztScore {{
    font-size: 40px;
    font-weight: 920;
    color: white;
    letter-spacing: -1px;
}}
QFrame#ztSignalCard, QFrame#ztSummaryCard, QFrame#ztEvidence {{
    background: rgba(11, 19, 38, 226);
    border: 1px solid rgba(70, 86, 126, 102);
    border-radius: 18px;
}}
QFrame#ztSignalCard:hover, QFrame#ztSummaryCard:hover {{
    background: rgba(15, 26, 50, 238);
    border: 1px solid rgba(34, 211, 238, 105);
}}
QFrame#ztSignalCard[tone="good"] {{ border: 1px solid rgba(52, 211, 153, 86); }}
QFrame#ztSignalCard[tone="warn"] {{ border: 1px solid rgba(251, 191, 36, 88); }}
QFrame#ztSignalCard[tone="danger"] {{ border: 1px solid rgba(251, 113, 133, 92); }}
QFrame#ztEvidence {{
    background: rgba(6, 11, 24, 150);
    border: 1px solid rgba(34, 211, 238, 50);
}}
QPushButton#ztActionCard {{
    text-align: left;
    padding: 16px 18px;
    border-radius: 18px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(18, 31, 58, 242), stop:1 rgba(8, 15, 31, 242));
    border: 1px solid rgba(76, 92, 130, 105);
    font-size: 13px;
    font-weight: 820;
    line-height: 1.45;
}}
QPushButton#ztActionCard:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(24, 39, 74, 250), stop:1 rgba(10, 22, 44, 250));
    border: 1px solid rgba(34, 211, 238, 125);
}}
/* Command palette --------------------------------------------------------- */
QDialog#commandPalette {{
    background: qradialgradient(cx:0.5, cy:0.0, radius:1.0, stop:0 #132040, stop:0.42 #0B1223, stop:1 #050812);
}}
QLineEdit#commandSearch {{
    min-height: 50px;
    border-radius: 16px;
    padding: 0 18px;
    font-size: 18px;
    font-weight: 720;
    background: rgba(6, 11, 24, 210);
    border: 1px solid rgba(34, 211, 238, 92);
}}
QListWidget#commandResults {{
    background: rgba(6, 11, 24, 118);
    border: 1px solid rgba(70, 86, 126, 94);
    border-radius: 18px;
    padding: 8px;
}}
QListWidget#commandResults::item {{
    min-height: 56px;
    padding: 10px 12px;
    margin: 3px;
    border-radius: 14px;
}}
QListWidget#commandResults::item:selected {{
    background: rgba(91, 108, 255, 95);
    color: white;
}}

"""
