from pathlib import Path
import shutil
import getpass
import os
import tarfile
import datetime
import sys
import argparse
import zipfile

def zipdir(path, ziph):
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file), 
                       os.path.relpath(os.path.join(root, file), 
                                     os.path.join(path, '..')))
# Optionales Paket für den Papierkorb (send2trash) laden, falls vorhanden
try:
    import send2trash
    HAS_SEND2TRASH = True
except ImportError:
    HAS_SEND2TRASH = False

try:
    shutil.rmtree("tmp", ignore_errors=True)
except:
    pass

def remove_readonly(func, path, excinfo):
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)

def safe_delete(path_to_delete):
    """Verschiebt eine Datei oder einen Ordner sicher in den Papierkorb (via send2trash) 
    oder nutzt shutil als Fallback, falls das Paket nicht installiert ist."""
    try:
        if HAS_SEND2TRASH:
            send2trash.send2trash(str(path_to_delete))
        else:
            import stat
            def onerror(func, p, exc):
                os.chmod(p, stat.S_IWRITE)
                func(p)
            if Path(path_to_delete).is_dir():
                shutil.rmtree(path_to_delete, onerror=onerror)
            else:
                os.chmod(path_to_delete, stat.S_IWRITE)
                os.remove(path_to_delete)
    except Exception as e:
            print(f"-> Warnung: Konnte '{path_to_delete.name}' nicht in den Papierkorb verschieben: {e}")

def run_backup(extra_input=None, interactive=False):
    if interactive:
        extra = input("Haben Sie noch zusätzliche Ordner die gesichert werden sollen \n\t( außer Dokumente, Downloads, Bilder, Videos und Desktop ) \n\t( Bitte trennen mit \",\" ohne Leerzeichen vor und nach dem Komma )\n > ").strip()
    else:
        extra = extra_input.strip() if extra_input else ""

    script_dir = Path(__file__).resolve().parent
    tmp_path = script_dir / "tmp"
    tmp_path.mkdir(parents=True, exist_ok=True)

    home = Path.home()
    cu = getpass.getuser().lower()
    
    standard_ordner = {
        "Documents": home / "Documents",
        "Downloads": home / "Downloads",
        "Pictures": home / "Pictures",
        "Videos": home / "Videos",
        "Desktop": home / "Desktop"
    }
    
    zu_sichernde_ordner = {}
    
    for name, pfad in standard_ordner.items():
        if pfad.exists():
            zu_sichernde_ordner[name] = pfad

    if extra:
        extra_pfade = extra.split(',')
        for ep in extra_pfade:
            ep = ep.strip()
            if not ep:
                continue
            
            p = Path(ep)
            if not p.is_absolute():
                p = (script_dir / p).resolve()
            
            if p.exists() and p.is_dir():
                zu_sichernde_ordner[p.name] = p
            else:
                print(f"-> Warnung: Zusätzlicher Pfad '{ep}' wurde nicht gefunden oder ist kein Ordner.")

    if not zu_sichernde_ordner:
        print("-> Keine gültigen Ordner zum Sichern gefunden!")
        return
    
    os.system("cls")

    for ordner_name, quell_pfad in zu_sichernde_ordner.items():
        ziel_pfad = tmp_path / ordner_name

        print(f"Kopiere {ordner_name} ({quell_pfad})...")
        try:
            def ignore_errors(dir, files):
                ignored = []
                for f in files:
                    fp = os.path.join(dir, f)
                    if not os.access(fp, os.R_OK):
                        ignored.append(f)
                return ignored

            shutil.copytree(quell_pfad, ziel_pfad, dirs_exist_ok=True, ignore=ignore_errors)
    
            reco_file = ziel_pfad / "reco.recc"
            quell_str = str(quell_pfad)
            quell_str_angepasst = quell_str.replace(cu, "{cu}")

            with open(reco_file, "w", encoding="utf-8") as f:
                f.write(f"qp:{quell_str_angepasst}")
                
            print(f"-> {ordner_name} erfolgreich gesichert.")
        except Exception as e:
            print(f"-> Fehler beim Kopieren von {ordner_name}: {e}")
            reco_file = ziel_pfad / "reco.recc"
            quell_str = str(quell_pfad)
            quell_str_angepasst = quell_str.replace(cu, "{cu}")

            with open(reco_file, "w", encoding="utf-8") as f:
                f.write(f"qp:{quell_str_angepasst}")
            print(" -> Recognisionfile created")
    
    print("===========================================")
    print("==             Erstelle Archiv           ==")
    print("===========================================")
    os.system("cls")

    def size_format(b):
        if b < 1000:
                  return '%i' % b + 'B'
        elif 1000 <= b < 1000000:
            return '%.1f' % float(b/1000) + 'KB'
        elif 1000000 <= b < 1000000000:
            return '%.1f' % float(b/1000000) + 'MB'
        elif 1000000000 <= b < 1000000000000:
            return '%.1f' % float(b/1000000000) + 'GB'
        elif 1000000000000 <= b:
            return '%.1f' % float(b/1000000000000) + 'TB'

    def get_size(start_path = '.'):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(start_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # skip if it is symbolic link
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)

        return total_size

    os.system("cls")

    archive_name = script_dir / 'backup_{date:%Y-%m-%d_%H-%M-%S}.zip'.format(date=datetime.datetime.now())
    print("Archive Name: ", archive_name.name)
    
    print()
    with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipdir(str(tmp_path), zipf)
    
    print("===========================================")
    print("==            Archiv Erstellt            ==")
    print("===========================================")

    shutil.rmtree(tmp_path, onerror=remove_readonly)

def run_restore(zip_filename=None):
    print("===========================================")
    print("==       Starte Wiederherstellung        ==")
    print("===========================================")

    if not HAS_SEND2TRASH:
        print("Hinweis: Das Paket 'send2trash' ist nicht installiert.")
        print("Um Dateien sicher in den Papierkorb zu verschieben, führe bitte aus:")
        print("pip install send2trash\n")

    script_dir = Path(__file__).resolve().parent
    
    if zip_filename:
        selected_zip = script_dir / zip_filename
        if not selected_zip.exists():
            print(f"-> Das angegebene Archiv '{zip_filename}' wurde nicht gefunden!")
            return
    else:
        zip_dateien = list(script_dir.glob("backup_*.zip"))
        
        if not zip_dateien:
            print("-> Keine Backup-Archive (backup_*.zip) gefunden!")
            return

        print("Verfügbare Backup-Archive:")
        for idx, z_file in enumerate(zip_dateien):
            print(f"  [{idx + 1}] {z_file.name}")

        wahl = input("Wähle die Nummer des Archives aus: ")
        try:
            wahl_idx = int(wahl) - 1
            selected_zip = zip_dateien[wahl_idx]
        except (ValueError, IndexError):
            print("-> Ungültige Auswahl!")
            return

    extract_tmp = script_dir / "restore_tmp"
    if extract_tmp.exists():
        shutil.rmtree(extract_tmp, onerror=remove_readonly)
    extract_tmp.mkdir(parents=True, exist_ok=True)

    print(f"Entpacke {selected_zip.name}...")
    with zipfile.ZipFile(selected_zip, 'r') as zipf:
        zipf.extractall(extract_tmp)

    current_user = getpass.getuser().lower()
    print(f"Aktueller Benutzer für Wiederherstellung: {current_user}")

    reco_dateien = list(extract_tmp.glob("**/reco.recc"))
    
    if not reco_dateien:
        print("-> Keine Wiederherstellungsdateien (reco.recc) im Archiv gefunden.")
        shutil.rmtree(extract_tmp, onerror=remove_readonly)
        return

    for reco_file in reco_dateien:
        backup_ordner = reco_file.parent
        ordner_name = backup_ordner.name

        try:
            with open(reco_file, "r", encoding="utf-8") as f:
                inhalt = f.read()
                
            if inhalt.startswith("qp:"):
                pfad_template = inhalt.split("qp:")[1]
                ziel_pfad_str = pfad_template.replace("{cu}", current_user)
                ziel_pfad = Path(ziel_pfad_str)

                print(f"Stelle '{ordner_name}' wieder her nach: {ziel_pfad}")
                ziel_pfad.mkdir(parents=True, exist_ok=True)

                backup_rel_pfad = set()
                for item in backup_ordner.rglob("*"):
                    if item.name == "reco.recc":
                        continue
                    backup_rel_pfad.add(item.relative_to(backup_ordner))

                if ziel_pfad.exists():
                    for existing_item in sorted(ziel_pfad.rglob("*"), reverse=True):
                        if existing_item.name == "reco.recc":
                            continue
                        
                        rel_path = existing_item.relative_to(ziel_pfad)
                        if rel_path not in backup_rel_pfad:
                            print(f"-> Verschiebe nicht im Backup enthaltene Datei/Ordner in den Papierkorb: {rel_path}")
                            safe_delete(existing_item)

                for item in backup_ordner.iterdir():
                    if item.name == "reco.recc":
                        continue
                    
                    target_item = ziel_pfad / item.name
                    
                    if item.name.lower() == "desktop.ini":
                        if target_item.exists():
                            try:
                                import stat
                                os.chmod(target_item, stat.S_IWRITE)
                            except Exception:
                                pass

                    if item.is_dir():
                        shutil.copytree(item, target_item, dirs_exist_ok=True)
                    else:
                        try:
                            shutil.copy2(item, target_item)
                        except PermissionError:
                            try:
                                import stat
                                os.chmod(target_item, stat.S_IWRITE)
                                shutil.copy2(item, target_item)
                            except Exception as sub_e:
                                print(f"-> Warnung: Konnte {item.name} nicht überschreiben ({sub_e})")
                        
                print(f"-> {ordner_name} erfolgreich wiederhergestellt.")
        except Exception as e:
            print(f"-> Fehler bei der Wiederherstellung von {ordner_name}: {e}")

    shutil.rmtree(extract_tmp, onerror=remove_readonly)
    print("===========================================")
    print("==      Wiederherstellung beendet        ==")
    print("===========================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup & Recovery Tool")
    subparsers = parser.add_subparsers(dest="command")

    # Subparser für 'backup'
    parser_backup = subparsers.add_parser("backup", help="Erstellt ein Backup")
    parser_backup.add_argument("--extras", type=str, default=None, help="Zusätzliche Ordner, getrennt durch Komma")

    # Subparser für 'restore'
    parser_restore = subparsers.add_parser("restore", help="Stellt ein Backup wieder her")
    parser_restore.add_argument("tarfile", nargs="?", default=None, help="Name der Backup-Archiv-Datei (optional)")

    args = parser.parse_args()

    if args.command == "backup":
        run_backup(args.extras, interactive=False)
    elif args.command == "restore":
        if not args.tarfile:
            script_dir = Path(__file__).resolve().parent
            tar_dateien = sorted(list(script_dir.glob("backup_*.tar.xz")) + list(script_dir.glob("backup_*.tar.gz")) + list(script_dir.glob("backup_*.zip")), key=os.path.getmtime, reverse=True)
            if tar_dateien:
                args.tarfile = tar_dateien[0].name
                print(f"-> Kein Dateiname angegeben. Nutze automatisch das neueste Backup: {args.tarfile}")
        run_restore(args.tarfile)
    else:
        os.system("title \"Backup & Recovery Tool\"")
        os.system("cls")
        # Interaktiver Fallback, wenn das Skript ohne Parameter gestartet wird
        print("===========================================")
        print("==       Backup & Recovery Tool          ==")
        print("===========================================")
        print(" [1] Backup erstellen")
        print(" [2] Wiederherstellen (Restore)")
        
        modus = input("Bitte Modus wählen (1 oder 2): ").strip()
        
        os.system("cls")
        
        if modus == "1":
            run_backup(interactive=True)
        elif modus == "2":
            run_restore()
        else:
            print("Ungültige Eingabe. Programm wird beendet.")