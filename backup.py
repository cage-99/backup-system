from pathlib import Path
import shutil
import getpass
import os
import datetime
import sys
import argparse
import zipfile
import tempfile
import stat

# Optionales Paket für den Papierkorb (send2trash) laden, falls vorhanden
try:
    import send2trash
    HAS_SEND2TRASH = True
except ImportError:
    HAS_SEND2TRASH = False

def remove_readonly(func, path, excinfo):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        print(f"-> Konnte Schreibschutz nicht entfernen für {path}: {e}")

def safe_delete(path_to_delete):
    p = Path(path_to_delete)
    if not p.exists():
        return
    try:
        # Vorab immer den Schreibschutz erzwingen, damit Windows das Löschen nicht blockiert
        if p.is_file() or p.is_symlink():
            os.chmod(p, stat.S_IWRITE)
        
        if HAS_SEND2TRASH:
            try:
                send2trash.send2trash(str(p))
                return
            except Exception:
                # Fallback auf normales Löschen, falls send2trash fehlschlägt
                pass

        if p.is_dir():
            shutil.rmtree(p, onerror=remove_readonly)
        else:
            p.unlink()
    except Exception as e:
        print(f"-> Fehler beim Löschen von '{p.name}': {e}")

def robust_copy(src_dir, dst_dir):
    """Kopiert Ordner robust Datei für Datei. Überspringt geschützte Dateien/Links."""
    src_path = Path(src_dir)
    dst_path = Path(dst_dir)
    dst_path.mkdir(parents=True, exist_ok=True)
    
    script_dir = Path(__file__).resolve().parent.resolve()
    copied_files = 0

    for root, dirs, files in os.walk(src_dir):
        root_p = Path(root).resolve()
        
        if script_dir in root_p.parents or root_p == script_dir:
            continue
            
        try:
            rel_path = root_p.relative_to(src_path)
        except ValueError:
            continue
            
        target_subdir = dst_path / rel_path
        
        try:
            target_subdir.mkdir(parents=True, exist_ok=True)
        except Exception:
            continue

        for file in files:
            if file.lower() == "reco.recc":
                continue

            src_file = root_p / file
            
            try:
                if src_file.is_symlink() or (src_file.is_dir() and src_file.lstat().st_file_attributes & 0x400):
                    continue
            except Exception:
                pass

            target_file = target_subdir / file
            
            try:
                if not os.access(src_file, os.R_OK):
                    continue
                shutil.copy2(src_file, target_file)
                copied_files += 1
            except Exception:
                pass
                
    return copied_files

def run_backup(extra_input=None, interactive=False):
    if interactive:
        extra = input("Haben Sie noch zusätzliche Ordner die gesichert werden sollen \n\t( außer Dokumente, Downloads, Bilder, Videos und Desktop ) \n\t( Bitte trennen mit \",\" ohne Leerzeichen vor und nach dem Komma )\n > ").strip()
    else:
        extra = extra_input.strip() if extra_input else ""

    script_dir = Path(__file__).resolve().parent
    
    # Temporärer Ordner sicher im System-Temp anlegen, damit er nicht im Backup landet
    tmp_path = Path(tempfile.gettempdir()) / "backup_sys_tmp"
    if tmp_path.exists():
        shutil.rmtree(tmp_path, onerror=remove_readonly, ignore_errors=True)
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
            anzahl = robust_copy(quell_pfad, ziel_pfad)
    
            reco_file = ziel_pfad / "reco.recc"
            quell_str = str(quell_pfad)
            quell_str_angepasst = quell_str.replace(cu, "{cu}")

            with open(reco_file, "w", encoding="utf-8") as f:
                f.write(f"qp:{quell_str_angepasst}")
                
            print(f"-> {ordner_name} erfolgreich gesichert ({anzahl} Dateien kopiert).")
        except Exception as e:
            print(f"-> Fehler beim Sichern von {ordner_name}: {e}")

    print("===========================================")
    print("==             Erstelle Archiv           ==")
    print("===========================================")

    archive_name = script_dir / 'backup_{date:%Y-%m-%d_%H-%M-%S}.zip'.format(date=datetime.datetime.now())
    print("Archive Name: ", archive_name.name)
    
    print()
    total_zipped = 0
    with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in tmp_path.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(tmp_path)
                zipf.write(file_path, arcname)
                total_zipped += 1

    print(f"-> Archiv erfolgreich erstellt ({total_zipped} Dateien im ZIP enthalten).")
    print("===========================================")
    print("==            Archiv Erstellt            ==")
    print("===========================================")

    shutil.rmtree(tmp_path, onerror=remove_readonly, ignore_errors=True)

def run_restore(zip_filename=None):
    print("===========================================")
    print("==        Starte Wiederherstellung       ==")
    print("===========================================")

    if not HAS_SEND2TRASH:
        print("Hinweis: Das Paket 'send2trash' ist nicht installiert.")
        print("Um Dateien sicher in den Papierkorb zu verschieben, führe bitte aus:")
        print("pip install send2trash\n")

    script_dir = Path(__file__).resolve().parent.resolve()
    
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

    # WICHTIG: r_tmp wird im Windows-Temp-Verzeichnis erstellt, damit das Skript sich nicht selbst löscht!
    extract_tmp = Path(tempfile.gettempdir()) / "backup_sys_r_tmp"
    if extract_tmp.exists():
        shutil.rmtree(extract_tmp, onerror=remove_readonly, ignore_errors=True)
    extract_tmp.mkdir(parents=True, exist_ok=True)

    print(f"Entpacke {selected_zip.name}...")
    with zipfile.ZipFile(selected_zip, 'r') as zipf:
        zipf.extractall(extract_tmp)

    current_user = getpass.getuser().lower()
    print(f"Aktueller Benutzer für Wiederherstellung: {current_user}")

    reco_dateien = list(extract_tmp.rglob("reco.recc"))
    
    if not reco_dateien:
        print("-> Keine gültigen Wiederherstellungsdateien (reco.recc) im Archiv gefunden.")
        shutil.rmtree(extract_tmp, onerror=remove_readonly, ignore_errors=True)
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
                ziel_pfad = Path(ziel_pfad_str).resolve()

                if "Administrator" in str(ziel_pfad) and current_user != "administrator":
                    ziel_pfad = Path(str(ziel_pfad).replace("C:\\Users\\Administrator", f"C:\\Users\\{getpass.getuser()}"))

                print(f"\nStelle '{ordner_name}' wieder her nach: {ziel_pfad}")
                
                try:
                    ziel_pfad.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass

                if not ziel_pfad.exists():
                    print(f"-> Warnung: Zielpfad konnte nicht erstellt werden: {ziel_pfad}")
                    continue

                backup_rel_pfad = set()
                for item in backup_ordner.rglob("*"):
                    if item.name.lower() == "reco.recc":
                        continue
                    backup_rel_pfad.add(item.relative_to(backup_ordner))

                if ziel_pfad.exists():
                    for existing_item in sorted(ziel_pfad.rglob("*"), reverse=True):
                        if existing_item.name.lower() == "reco.recc":
                            continue
                        
                        try:
                            resolved_item = existing_item.resolve()
                            
                            # ABSOLUTER SELBSTSCHUTZ: 
                            if script_dir in resolved_item.parents or resolved_item == script_dir:
                                continue
                        except Exception:
                            pass
                        
                        try:
                            if existing_item.is_symlink() or (existing_item.is_dir() and existing_item.lstat().st_file_attributes & 0x400):
                                continue
                        except Exception:
                            pass

                        rel_path = existing_item.relative_to(ziel_pfad)
                        if "backup-system" in str(rel_path):
                            continue
                        if rel_path not in backup_rel_pfad:
                            print(f"-> [Lösche / Papierkorb] Nicht im Backup enthalten: {rel_path}")
                            safe_delete(existing_item)

                for item in backup_ordner.rglob("*"):
                    if item.name.lower() == "reco.recc":
                        continue
                    
                    rel_path = item.relative_to(backup_ordner)
                    target_item = ziel_pfad / rel_path
                    
                    if item.is_dir():
                        target_item.mkdir(parents=True, exist_ok=True)
                    else:
                        target_item.parent.mkdir(parents=True, exist_ok=True)
                        if target_item.name.lower() == "desktop.ini" and target_item.exists():
                            try:
                                os.chmod(target_item, stat.S_IWRITE)
                            except Exception:
                                pass
                        try:
                            shutil.copy2(item, target_item)
                        except PermissionError:
                            try:
                                os.chmod(target_item, stat.S_IWRITE)
                                shutil.copy2(item, target_item)
                            except Exception as sub_e:
                                if "desktop.ini" not in str(target_item).lower():
                                    print(f"-> Warnung: Konnte {rel_path} nicht überschreiben ({sub_e})")
                        
                ziel_reco = ziel_pfad / "reco.recc"
                if ziel_reco.exists():
                    safe_delete(ziel_reco)

                print(f"-> {ordner_name} erfolgreich wiederhergestellt.")
        except Exception as e:
            print(f"-> Fehler bei der Wiederherstellung von {ordner_name}: {e}")

    if extract_tmp.exists():
        shutil.rmtree(extract_tmp, onerror=remove_readonly, ignore_errors=True)
        
    print("===========================================")
    print("==      Wiederherstellung beendet        ==")
    print("===========================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup & Recovery Tool")
    subparsers = parser.add_subparsers(dest="command")

    parser_backup = subparsers.add_parser("backup", help="Erstellt ein Backup")
    parser_backup.add_argument("--extras", type=str, default=None, help="Zusätzliche Ordner, getrennt durch Komma")

    parser_restore = subparsers.add_parser("restore", help="Stellt ein Backup wieder her")
    parser_restore.add_argument("tarfile", nargs="?", default=None, help="Name der Backup-Archiv-Datei (optional)")

    args = parser.parse_args()

    if args.command == "backup":
        run_backup(args.extras, interactive=False)
    elif args.command == "restore":
        if not args.tarfile:
            script_dir = Path(__file__).resolve().parent
            tar_dateien = sorted(list(script_dir.glob("backup_*.zip")), key=os.path.getmtime, reverse=True)
            if tar_dateien:
                args.tarfile = tar_dateien[0].name
                print(f"-> Kein Dateiname angegeben. Nutze automatisch das neueste Backup: {args.tarfile}")
        run_restore(args.tarfile)
    else:
        os.system("title \"Backup & Recovery Tool\"")
        os.system("cls")
        print("===========================================")
        print("==        Backup & Recovery Tool         ==")
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
