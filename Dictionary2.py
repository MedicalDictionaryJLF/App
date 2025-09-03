import csv
import os
import random
import tkinter as tk
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.widget import Widget
from kivy.graphics import Rectangle, Color
from Encryption.cipher import encrypt, decrypt, load_key
from translations import translations
from threading import Thread
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

USER_DETAILS_DIR = r"C:\Users\Daniel\OneDrive - Univerzita Komenskeho v Bratislave\ŠVOČ\Dictionary 2\Users details"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDICAL_TERMS_FILE = os.path.join(BASE_DIR, 'medical_terms.csv')
USERS_FILE = os.path.join(BASE_DIR, 'users.csv')
SECRET_KEY_FILE = r'C:\Users\Daniel\OneDrive - Univerzita Komenskeho v Bratislave\ŠVOČ\Dictionary 2\Encryption\secret.key'
MASTER_SECRET = load_key(SECRET_KEY_FILE)

if not os.path.exists(MEDICAL_TERMS_FILE):
    print(f"Error: File '{MEDICAL_TERMS_FILE}' not found!")
    print(f"Current Working Directory: {os.getcwd()}")
    print(f"Files in Directory: {os.listdir(os.getcwd())}")
else:
    print(f"File '{MEDICAL_TERMS_FILE}' found successfully!")

# Google Drive folder ID (replace with your actual one)
DRIVE_FOLDER_ID = "1lpDi_PC57rfttjELAHI4xQwgWtsRQnqQ"

def get_drive_client():
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile("credentials.json")
    if gauth.credentials is None:
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()
    gauth.SaveCredentialsFile("credentials.json")
    return GoogleDrive(gauth)

def drive_file_exists(drive, remote_name):
    query = f"title = '{remote_name}' and '{DRIVE_FOLDER_ID}' in parents and trashed = false"
    return bool(drive.ListFile({'q': query}).GetList())

def upload_csv_if_not_exists(username, file_type, local_path):
    if file_type not in {"MT_added", "review"}:
        raise ValueError("Invalid file_type")
    drive = get_drive_client()
    remote_name = f"{username}_{file_type}.csv"
    if drive_file_exists(drive, remote_name):
        return False
    gfile = drive.CreateFile({'title': remote_name, 'parents': [{'id': DRIVE_FOLDER_ID}]})
    gfile.SetContentFile(local_path)
    gfile.Upload()
    return True

def upload_user_files_if_missing(username, user_files_dict):
    def task():
        for file_type in ("MT_added", "review"):
            local_path = user_files_dict["added_terms"] if file_type == "MT_added" else user_files_dict["review"]
            try:
                uploaded = upload_csv_if_not_exists(username, file_type, local_path)
                print(f"[Drive] {file_type} → uploaded={uploaded}")
            except Exception as e:
                print(f"[Drive ERROR] {file_type} → {e}")
    Thread(target=task, daemon=True).start()

def check_user_drive_files(username):
    missing = []
    try:
        drive = get_drive_client()
        for file_type in ("MT_added", "review"):
            remote_name = f"{username}_{file_type}.csv"
            if not drive_file_exists(drive, remote_name):
                missing.append(remote_name)
    except Exception as e:
        missing.append(f"[Drive Error] {e}")
    return missing

def search_term(query, filename=MEDICAL_TERMS_FILE):
    results = []
    try:
        with open(filename, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            expected = {'latin_translation','genitive',
                'accusative','gender','declination',
                'english_translation','english_definition',
                'german_translation','german_definition',
                'slovak_translation','slovak_definition',
                'spanish_translation','spanish_definition'}
            missing = expected - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"CSV missing columns: {', '.join(sorted(missing))}")
            q = query.lower()
            trans_fields = ['latin_translation','english_translation','german_translation','slovak_translation',
                            'spanish_translation','icelandic_translation','norwegian_translation']
            for row in reader:
                if any(q in (row.get(field,'') or '').lower() for field in trans_fields):
                    results.append(row)
    except Exception as e:
        raise RuntimeError(f"Error during search: {e}")
    return results

def get_user_files(username):
    """Return dict with personalized file paths for the user."""
    safe_username = username.replace(" ", "_").replace(".", "_").replace("@", "_")
    added = os.path.join(USER_DETAILS_DIR, f"{safe_username}_MT_added.csv")
    review = os.path.join(USER_DETAILS_DIR, f"{safe_username}_review.csv")
    return {"added_terms": added, "review": review}

def ensure_user_details_dir():
    if not os.path.exists(USER_DETAILS_DIR):
        os.makedirs(USER_DETAILS_DIR, exist_ok=True)

def save_term(data, filename):
    """Save the entered term into the user's personalized added terms file."""
    correct_header = [
        'noun','adjective','verb','preposition','phrase',
        'latin_translation','genitive','accusative','gender','declination',
        'english_translation','english_definition',
        'german_translation','slovak_translation',
        'german_definition','slovak_definition',
        'spanish_translation','spanish_definition',
        'norvegian_translation','norwegian_definition',
        'icelandic_translation','icelandic_definition'
    ]
    file_exists = os.path.exists(filename)
    with open(filename, 'a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(correct_header)
        writer.writerow(data)
    print(f"New term successfully added: {data}")

def register_user(username, password):
    needs_header = not os.path.exists(USERS_FILE) or os.stat(USERS_FILE).st_size == 0
    with open(USERS_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if needs_header:
            writer.writerow(['username', 'encrypted_password'])
        encrypted_pw = encrypt(password, MASTER_SECRET)
        writer.writerow([username, encrypted_pw])

def user_exists(username):
    if not os.path.exists(USERS_FILE):
        return False
    with open(USERS_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('username') == username:
                return True
    return False

def check_credentials(username, password):
    if not os.path.exists(USERS_FILE):
        return False
    with open(USERS_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('username') == username:
                try:
                    decrypted_pw = decrypt(row['encrypted_password'], MASTER_SECRET)
                    return decrypted_pw == password
                except Exception:
                    return False
    return False

class MenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.root_layout = FloatLayout()
        self.add_widget(self.root_layout)

        with self.root_layout.canvas.before:
            Color(1, 1, 1, 0.25)
            self.bg_rect = Rectangle(source='background.jpg', pos=self.pos, size=self.size)

        self.root_layout.bind(size=self._update_bg_rect, pos=self._update_bg_rect)

        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=15, size_hint=(0.5, None), height=400, pos_hint={"center_x": 0.5, "center_y": 0.5})
        self.root_layout.add_widget(self.layout)

        language_order = [
            ("English", "English"),
            ("Deutch", "Deutch"),
            ("Slovensky", "Slovensky"),
            ("Spanish", "Español"),
            ("Norwegian", "Norsk"),
            ("Icelandic", "Íslenska")
        ]
        for lang_key, display_name in language_order:
            if lang_key in translations:
                btn = Button(text=display_name, size_hint=(1, None), font_size=25, height=60, pos_hint={"center_x": 0.5})
                btn.bind(on_release=lambda inst, l=lang_key: self.set_language_by_key(l))
                self.layout.add_widget(btn)

    def set_language_by_key(self, lang_key):
        self.manager.transition.direction = "left"
        self.manager.language = lang_key
        self.manager.current = 'login'

    def _update_bg_rect(self, *args):
        self.bg_rect.pos = self.root_layout.pos
        self.bg_rect.size = self.root_layout.size

class LoginRegisterScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root_layout = FloatLayout()
        self.add_widget(self.root_layout)
        with self.root_layout.canvas.before:
            Color(1, 1, 1, 0.25)
            self.bg_rect = Rectangle(source='background.jpg', pos=self.pos, size=self.size)
        self.root_layout.bind(size=self._update_bg_rect, pos=self._update_bg_rect)
        self.layout = BoxLayout(orientation='vertical', padding=40, spacing=20)
        self.root_layout.add_widget(self.layout)
        self.info_label = Label(text='', font_size=32, size_hint=(1, None), height=60)
        self.layout.add_widget(self.info_label)
        self.state = 'choice'
        self.build_choice()

    def on_pre_enter(self):
        self.update_texts()

    def update_texts(self):
        lang = getattr(self.manager, 'language', 'English')
        t = lambda k, default=None: translations[lang].get(k, default or k)
        if self.state == 'choice':
            self.info_label.text = t('Login or Register')
            self.login_btn.text = t('Login')
            self.register_btn.text = t('Register')
        elif self.state == 'login':
            self.info_label.text = t('Login')
            self.username_input.hint_text = t('Username')
            self.password_input.hint_text = t('Password')
            self.enter_btn.text = t('Enter')
            self.return_btn.text = t('Return')
        elif self.state == 'register':
            self.info_label.text = t('Register')
            self.username_input.hint_text = t('Username')
            self.password_input.hint_text = t('Password')
            self.password_confirm_input.hint_text = t('Confirm Password')
            self.enter_btn.text = t('Enter')
            self.return_btn.text = t('Return')

    def _update_bg_rect(self, *args):
        self.bg_rect.pos = self.root_layout.pos
        self.bg_rect.size = self.root_layout.size

    def clear_layout(self):
        self.layout.clear_widgets()
        self.layout.add_widget(self.info_label)

    def build_choice(self):
        self.clear_layout()
        btn_row = BoxLayout(orientation='horizontal', spacing=20, size_hint=(1, None), height=60)
        self.login_btn = Button()
        self.register_btn = Button()
        btn_row.add_widget(self.login_btn)
        btn_row.add_widget(self.register_btn)
        self.layout.add_widget(btn_row)
        self.login_btn.bind(on_release=self.show_login)
        self.register_btn.bind(on_release=self.show_register)
        self.state = 'choice'
        self.update_texts()

    def show_login(self, instance):
        self.clear_layout()
        self.username_input = TextInput(multiline=False, font_size=24, size_hint=(1, None), height=50)
        self.password_input = TextInput(multiline=False, password=True, font_size=24, size_hint=(1, None), height=50)
        self.layout.add_widget(self.username_input)
        self.layout.add_widget(self.password_input)
        btn_row = BoxLayout(orientation='horizontal', spacing=20, size_hint=(1, None), height=60)
        self.enter_btn = Button()
        self.return_btn = Button()
        btn_row.add_widget(self.enter_btn)
        btn_row.add_widget(self.return_btn)
        self.layout.add_widget(btn_row)
        self.enter_btn.bind(on_release=self.login)
        self.return_btn.bind(on_release=lambda x: self.build_choice())
        self.state = 'login'
        self.update_texts()

    def show_register(self, instance):
        self.clear_layout()
        self.username_input = TextInput(multiline=False, font_size=24, size_hint=(1, None), height=50)
        self.password_input = TextInput(multiline=False, password=True, font_size=24, size_hint=(1, None), height=50)
        self.password_confirm_input = TextInput(multiline=False, password=True, font_size=24, size_hint=(1, None), height=50)
        self.layout.add_widget(self.username_input)
        self.layout.add_widget(self.password_input)
        self.layout.add_widget(self.password_confirm_input)
        btn_row = BoxLayout(orientation='horizontal', spacing=20, size_hint=(1, None), height=60)
        self.enter_btn = Button()
        self.return_btn = Button()
        btn_row.add_widget(self.enter_btn)
        btn_row.add_widget(self.return_btn)
        self.layout.add_widget(btn_row)
        self.enter_btn.bind(on_release=self.register)
        self.return_btn.bind(on_release=lambda x: self.build_choice())
        self.state = 'register'
        self.update_texts()

    def login(self, instance):
        lang = getattr(self.manager, 'language', 'English')
        t = lambda k, default=None: translations[lang].get(k, default or k)
        username = self.username_input.text.strip()
        password = self.password_input.text.strip()
        if not username or not password:
            self.info_label.text = t('Please enter username and password.')
            return
        if check_credentials(username, password):
            missing = check_user_drive_files(username)
            if missing:
                self.info_label.text = "Missing on Drive: " + ", ".join(missing)
                return
            self.manager.player_name = username
            self.manager.app_name = username
            ensure_user_details_dir()
            self.manager.user_files = get_user_files(username)
            self.manager.user_details_dir = USER_DETAILS_DIR
            self.manager.transition.direction = 'left'
            self.manager.current = 'submenu'
        else:
            self.info_label.text = t('Invalid credentials.')

    def register(self, instance):
        lang = getattr(self.manager, 'language', 'English')
        t = lambda k, default=None: translations[lang].get(k, default or k)
        username = self.username_input.text.strip()
        password = self.password_input.text.strip()
        password_confirm = self.password_confirm_input.text.strip()
        if not username or not password or not password_confirm:
            self.info_label.text = t('Please fill all fields.')
            return
        if password != password_confirm:
            self.info_label.text = t('Passwords do not match.')
            return
        if user_exists(username):
            self.info_label.text = t('Username already exists.')
            return
        register_user(username, password)
        ensure_user_details_dir()
        self.manager.user_files = get_user_files(username)
        upload_user_files_if_missing(username, self.manager.user_files)
        self.manager.user_details_dir = USER_DETAILS_DIR
        self.info_label.text = t('Registration successful! You can now log in.')
        self.username_input.text = ''
        self.password_input.text = ''
        self.password_confirm_input.text = ''

class SubMenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root_layout = FloatLayout()
        self.add_widget(self.root_layout)
        with self.root_layout.canvas.before:
            Color(1, 1, 1, 0.25)
            self.bg_rect = Rectangle(source='background.jpg', pos=self.pos, size=self.size)
        self.root_layout.bind(size=self._update_bg_rect, pos=self._update_bg_rect)

        self.layout = BoxLayout(orientation='vertical', spacing=20, padding=20)
        self.root_layout.add_widget(self.layout)

        self.title = Label(text="", font_size=50, size_hint=(1, None), height=80)
        self.layout.add_widget(self.title)

        self.search_btn = Button(text="", size_hint=(1, None), height=60, font_size=25)
        self.search_btn.bind(on_release=self.open_field_popup)
        self.layout.add_widget(self.search_btn)

        self.add_btn = Button(text="", size_hint=(1, None), height=60, font_size=25)
        self.add_btn.bind(on_release=self.go_to_entry)
        self.layout.add_widget(self.add_btn)

        self.quiz_btn = Button(text="", size_hint=(1, None), height=60, font_size=25)
        self.quiz_btn.bind(on_release=self.go_to_quiz)
        self.layout.add_widget(self.quiz_btn)

        self.back_btn = Button(text="", size_hint=(1, None), height=50, font_size=25)
        self.back_btn.bind(on_release=self.go_to_menu)
        self.layout.add_widget(self.back_btn)

    def on_pre_enter(self):
        lang = self.manager.language
        self.title.text = translations[lang].get("welcome", "")
        self.search_btn.text = translations[lang].get("search_term", "")
        self.add_btn.text = translations[lang].get("add_term", "")
        self.quiz_btn.text = translations[lang].get("quiz", "")
        self.back_btn.text = translations[lang].get("back_lng", "")

    def go_to_menu(self, instance):
        self.manager.transition.direction = "right"
        self.manager.current = 'menu'

    def open_field_popup(self, instance):
        all_fields = [
            'latin_translation','genitive',
            'accusative','gender','declination',
            'english_translation','english_definition',
            'german_translation','german_definition',
            'slovak_translation','slovak_definition',
            'spanish_translation','spanish_definition',
            'norwegian_translation','norwegian_definition',
            'icelandic_translation','icelandic_definition'
        ]
        anchor_root = AnchorLayout(anchor_x='center', anchor_y='center')
        content = BoxLayout(orientation='vertical', spacing=15, padding=20,
                            size_hint=(None, None), size=(500, 600))
        grid = GridLayout(cols=2, spacing=10, size_hint=(1, None))
        grid.bind(minimum_height=grid.setter('height'))
        boxes = {}
        for key in all_fields:
            cell = BoxLayout(orientation='horizontal', spacing=5, size_hint_y=None, height=40)
            cb = CheckBox(active=(key in self.manager.selected_search_fields), size_hint=(None, None), size=(30, 30))
            lbl = Label(
                text=translations[self.manager.language].get(key, key.replace('_',' ').capitalize()),
                size_hint_x=1, halign='left', valign='middle'
            )
            lbl.bind(size=lambda lbl, sz: setattr(lbl, 'text_size', sz))
            cell.add_widget(cb)
            cell.add_widget(lbl)
            grid.add_widget(cell)
            boxes[key] = cb
        content.add_widget(grid)
        btn_box = AnchorLayout(anchor_x='center', anchor_y='bottom', size_hint=(1, None), height=60)
        ok = Button(text=translations[self.manager.language].get("OK", "OK"), size_hint=(None, None), size=(100, 40))
        btn_box.add_widget(ok)
        content.add_widget(btn_box)
        anchor_root.add_widget(content)

        popup = Popup(
            title=translations[self.manager.language].get("Select fields to show", "Select fields to show"),
            content=anchor_root,
            size_hint=(None, None),
            size=(600, 700),
            auto_dismiss=False
        )
        def on_ok(btn):
            self.manager.transition.direction = "left"
            self.manager.selected_search_fields = [k for k, v in boxes.items() if v.active]
            popup.dismiss()
            self.manager.current = 'search'
        ok.bind(on_release=on_ok)
        popup.open()

    def go_to_entry(self, instance):
        self.manager.transition.direction = "left"
        self.manager.current = 'entry'

    def go_to_quiz(self, instance):
        self.manager.transition.direction = "left"
        self.manager.current = 'quiz'

    def _update_bg_rect(self, *args):
        self.bg_rect.pos = self.root_layout.pos
        self.bg_rect.size = self.root_layout.size

class SearchScreen(Screen):
    def on_pre_enter(self):
        lang = self.manager.language
        self.search_input.hint_text = translations[lang].get("enter_term", "")
        self.search_btn.text = translations[lang].get("search", "")
        self.back_btn.text = translations[lang].get("back", "")
        self.last_search_text = ""
        self.search_results = []
        self.selected_word_row = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root_layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        self.add_widget(self.root_layout)
        with self.root_layout.canvas.before:
            Color(1,1,1,0.25)
            self.bg_rect = Rectangle(source='background.jpg', pos=self.pos, size=self.size)
        self.root_layout.bind(size=self._update_bg_rect, pos=self._update_bg_rect)

        bar = BoxLayout(size_hint_y=None, height=50, spacing=10)
        self.search_input = TextInput(font_size=25, multiline=False)
        self.search_input.bind(text=self.on_text_change)
        self.search_btn = Button(text="", size_hint_x=None, width=150, font_size=25)
        self.search_btn.bind(on_release=self.on_search)
        bar.add_widget(self.search_input)
        bar.add_widget(self.search_btn)
        self.root_layout.add_widget(bar)

        self.results_view = ScrollView()
        self.results_grid = GridLayout(cols=2, size_hint_y=None, spacing=10, padding=10)
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        self.results_view.add_widget(self.results_grid)
        self.root_layout.add_widget(self.results_view)

        self.back_btn = Button(text="", size_hint_y=None, height=50, font_size=25)
        self.back_btn.bind(on_release=self.back_to_menu)  # <-- fix: always use back_to_menu
        self.root_layout.add_widget(self.back_btn)

    def on_text_change(self, instance, value):
        if len(value.strip()) >= 2:
            self.on_search(None, live=True)
        else:
            self.results_grid.clear_widgets()

    def get_language_field(self):
        lang = self.manager.language
        if lang == "English":
            return "english_translation"
        elif lang == "Deutch":
            return "german_translation"
        elif lang == "Slovensky":
            return "slovak_translation"
        else:
            return "english_translation"

    def on_search(self, instance, live=False):
        term = self.search_input.text.strip()
        self.results_grid.clear_widgets()
        if len(term) < 2:
            if not live:
                self.output_message(
                    "Please enter a search term.",
                    "Bitte geben Sie einen Suchbegriff ein.",
                    "Zadajte hľadaný pojem.",
                    default="Please enter a search term."
                )
            return

        lang_field = self.get_language_field()
        try:
            results = []
            with open(MEDICAL_TERMS_FILE, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    value = (row.get(lang_field, '') or '').lower()
                    if value.startswith(term.lower()):
                        results.append(row)
            # Also search in personalized added terms
            user_files = getattr(self.manager, "user_files", None)
            added_terms_file = user_files["added_terms"] if user_files else None
            if added_terms_file and os.path.exists(added_terms_file):
                with open(added_terms_file, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        value = (row.get(lang_field, '') or '').lower()
                        if value.startswith(term.lower()):
                            results.append(row)
        except Exception as e:
            return self.output_message(
                f"Search failed: {e}",
                f"Suche fehlgeschlagen: {e}",
                f"Hľadanie zlyhalo: {e}",
                default="Search failed."
            )
        if not results:
            return self.output_message(
                "No matching results found.",
                "Keine Übereinstimmungen gefunden.",
                "Nenašli sa žiadne zodpovedajúce výsledky.",
                default="No matching results found."
            )
        self.search_results = results
        # Show clickable list of matching words in two columns
        shown_words = set()
        word_buttons = []
        for row in results:
            word = row.get(lang_field, '').strip()
            if word and word not in shown_words:
                btn = Button(text=word, size_hint_y=None, height=40)
                btn.bind(on_release=lambda btn, r=row: self.show_word_details(r))
                word_buttons.append(btn)
                shown_words.add(word)
        # Fill grid in two columns
        # If odd number, add an empty widget to keep grid shape
        if len(word_buttons) % 2 != 0:
            word_buttons.append(Widget(size_hint_y=None, height=40))
        for btn in word_buttons:
            self.results_grid.add_widget(btn)

    def show_word_details(self, row):
        # Show all selected fields for the selected word in two columns, filling down then across
        self.results_grid.clear_widgets()
        lang = self.manager.language
        fields = self.manager.selected_search_fields or []
        detail_widgets = []
        for key in fields:
            val = (row.get(key, '') or '').strip()
            if val:
                label_text = translations[lang].get(key, key.replace('_',' ').capitalize())
                detail_widgets.append(Label(text=f"{label_text}: {val}", size_hint_y=None, height=30))
        # Split into two columns, fill down then across
        n = len(detail_widgets)
        mid = (n + 1) // 2
        col1 = detail_widgets[:mid]
        col2 = detail_widgets[mid:]
        # Pad columns to equal length
        while len(col1) < len(col2):
            col1.append(Widget(size_hint_y=None, height=30))
        while len(col2) < len(col1):
            col2.append(Widget(size_hint_y=None, height=30))
        for i in range(len(col1)):
            self.results_grid.add_widget(col1[i])
            self.results_grid.add_widget(col2[i])
        # Add a back button centered across both columns
        from kivy.uix.boxlayout import BoxLayout
        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=50)
        btn_row.add_widget(Widget(size_hint_x=0.5))
        back_btn = Button(
            text=translations[lang].get("back to search", "Back to Search"),
            size_hint_x=None, width=200, height=40
        )
        back_btn.bind(on_release=lambda _: self.on_search(None, live=True))
        btn_row.add_widget(back_btn)
        btn_row.add_widget(Widget(size_hint_x=0.5))
        # Add the BoxLayout as a single widget spanning both columns
        self.results_grid.add_widget(btn_row)
        self.results_grid.add_widget(Widget(size_hint_y=None, height=0))

    def output_message(self, en, de, sk, default):
        msg = {
            'English': translations['English'].get(en, en),
            'Deutch': translations['Deutch'].get(de, de),
            'Slovensky': translations['Slovensky'].get(sk, sk)
        }.get(self.manager.language, default)
        self.results_grid.clear_widgets()
        # Center message across two columns
        label = Label(text=msg, size_hint_y=None, height=30, font_size=20, size_hint_x=1)
        self.results_grid.add_widget(label)
        self.results_grid.add_widget(Widget(size_hint_y=None, height=30))

    def back_to_menu(self, instance=None):
        self.manager.transition.direction = "right"
        self.manager.current = 'submenu'

    def _update_bg_rect(self, *args):
        self.bg_rect.pos = self.root_layout.pos
        self.bg_rect.size = self.root_layout.size
        
class EntryScreen(Screen):
    def on_pre_enter(self):
        """Update UI elements based on selected language."""
        lang = self.manager.language
        self.save_btn.text = translations[lang].get("Save Term", "Save Term")
        self.back_to_menu_btn.text = translations[lang].get("back", "Back")
        for field in self.inputs:
            self.inputs[field].hint_text = translations[lang].get(field, field.replace("_", " ").capitalize())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Fill the whole screen
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=10, size_hint=(1, 1), pos_hint={"center_x": 0.5, "center_y": 0.5})

        # Scrollable area for input fields
        scroll = ScrollView(size_hint=(1, 1), bar_width=10)
        input_grid = GridLayout(cols=2, spacing=10, size_hint_y=None, padding=10)
        input_grid.bind(minimum_height=input_grid.setter('height'))
        self.inputs = {}

        self.input_fields = [
            'latin_translation', 'genitive', 'accusative', 'gender', 'declination',
            'english_translation', 'english_definition', 'german_translation', 'slovak_translation', 'slovak_definition',
            'spanish_translation', 'spanish_definition',
            'norwegian_translation', 'norwegian_definition',
            'icelandic_translation', 'icelandic_definition'
        ]

        for field in self.input_fields:
            self.inputs[field] = TextInput(
                hint_text=field,
                multiline=True,  # Allow multiple lines
                font_size=25,
                size_hint_y=None,
                height=80,  # Taller for multiline
                padding=[10, 10, 10, 10]
            )
            input_grid.add_widget(self.inputs[field])

        scroll.add_widget(input_grid)
        self.layout.add_widget(scroll)

        self.save_btn = Button(text="", size_hint=(None, None), size=(250, 75), pos_hint={"center_x": 0.5}, font_size=25)
        self.save_btn.bind(on_release=self.save_term)
        self.layout.add_widget(self.save_btn)

        self.status_label = Label(text="", size_hint_y=None, height=30)
        self.layout.add_widget(self.status_label)

        # Define back_to_menu before binding!
        def back_to_menu(instance):
            self.manager.transition.direction = "right"
            self.manager.current = 'submenu'
        self.back_to_menu = back_to_menu

        self.button_row = BoxLayout(orientation='horizontal', spacing=10, padding=10, size_hint_y=None, height=50)
        self.back_to_menu_btn = Button(text="", size_hint=(1, None), size=(200, 50), pos_hint={"center_x": 0.5}, font_size=25)
        self.back_to_menu_btn.bind(on_release=self.back_to_menu)
        self.button_row.add_widget(self.back_to_menu_btn)

        self.layout.add_widget(self.button_row)
        self.add_widget(self.layout)

    def save_term(self, instance):
        """Save the entered term into user's personalized added terms file."""
        lang = self.manager.language
        blanks = [""] * 5
        data = blanks + [self.inputs[field].text.strip() for field in list(self.inputs)[5:]]
        user_files = getattr(self.manager, "user_files", None)
        added_terms_file = user_files["added_terms"] if user_files else None
        if any(data[5:]) and added_terms_file:
            save_term(data, added_terms_file)
            self.status_label.text = {
                "English": "Term saved successfully!",
                "Deutch": "Begriff erfolgreich gespeichert!",
                "Slovensky": "Pojem bol úspešne uložený!"
            }.get(lang, "Term saved successfully!")
            for field in self.inputs:
                self.inputs[field].text = ""
        else:
            self.status_label.text = {
                "English": "Please enter at least one field before saving.",
                "Deutch": "Bitte geben Sie mindestens ein Feld ein.",
                "Slovensky": "Zadajte aspoň jedno pole pred uložením."
            }.get(lang, "Please enter at least one field before saving.")

class QuizScreen(Screen):
    LANGUAGE_FIELD_MAP = {
        'english': 'english',
        'german': 'german',
        'slovak': 'slovak',
        'latin': 'latin',
        'spanish': 'spanish',
        'norwegian': 'norwegian',
        'icelandic': 'icelandic'
    }

    def on_pre_enter(self):
        lang = getattr(self.manager, 'language', 'English')
        self.start_quiz_btn.text = translations[lang].get('start_quiz', '')
        self.reset_btn.text = translations[lang].get('reset_quiz', '')
        self.back_btn.text = translations[lang].get('back', '')
        self.settings_btn.text = translations[lang].get('Quiz Settings', '')
        self.review_btn.text = translations[lang].get('Review Mistakes', '')
        self.status_label.text = ''
        self.score_label.text = f"{translations[lang].get('score','')}: {self.score} | {translations[lang].get('incorrect','')}: {self.incorrect}"

    def _update_bg_rect(self, *args):
        self.bg_rect.pos = self.root_layout.pos
        self.bg_rect.size = self.root_layout.size

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root_layout = FloatLayout()
        self.add_widget(self.root_layout)
        with self.root_layout.canvas.before:
            Color(1, 1, 1, 0.25)
            self.bg_rect = Rectangle(source='background.jpg', pos=self.pos, size=self.size)
        # Make sure _update_bg_rect is defined before this line!
        self.root_layout.bind(size=self._update_bg_rect, pos=self._update_bg_rect)

        # Only create layout once!
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        self.quiz_layout = BoxLayout(orientation='horizontal', size_hint_y=0.4, spacing=20)
        self.word_column_1 = GridLayout(cols=1, spacing=10, size_hint_x=0.5)
        self.word_column_2 = GridLayout(cols=1, spacing=10, size_hint_x=0.5)
        self.quiz_layout.add_widget(self.word_column_1)
        self.quiz_layout.add_widget(self.word_column_2)
        self.layout.add_widget(self.quiz_layout)
        controls = BoxLayout(orientation='horizontal', size_hint=(1,None), height=60, spacing=20)
        self.start_quiz_btn = Button(text='Start Quiz', font_size=25)
        self.start_quiz_btn.bind(on_press=self.start_quiz)
        self.reset_btn = Button(text='Reset Quiz', font_size=25)
        self.reset_btn.bind(on_press=self.reset_quiz)
        controls.add_widget(self.start_quiz_btn)
        controls.add_widget(self.reset_btn)
        self.layout.add_widget(controls)
        self.status_label = Label(text='', size_hint=(1,None), height=30, font_size=20)
        self.layout.add_widget(self.status_label)
        self.score_label = Label(text='', size_hint=(1,None), height=30, font_size=20)
        self.layout.add_widget(self.score_label)
        self.control_row = BoxLayout(orientation='horizontal', size_hint=(1,None), height=50, spacing=20)
        self.settings_btn = Button(text='Quiz Settings', font_size=25)
        self.settings_btn.bind(on_release=self.open_link_settings)
        self.review_btn = Button(text='Review Mistakes', font_size=25)
        self.review_btn.bind(on_release=self.open_review_popup)
        self.control_row.add_widget(self.settings_btn)
        self.control_row.add_widget(self.review_btn)
        self.layout.add_widget(self.control_row)
        self.back_btn = Button(text='Back to Menu', size_hint=(1,None), height=50, font_size=25)
        self.back_btn.bind(on_release=self.go_to_submenu)
        self.layout.add_widget(self.back_btn)
        self.root_layout.add_widget(self.layout)

        # State
        self.score = 0
        self.incorrect = 0
        self.source_items = []
        self.correct_targets = []
        self.selected_source = None
        self.selected_target = None
        self.link_type = None
        self.link_source_language = None
        self.link_target_language = None
        self.review_mode = False

        # Positive feedback is now in translations.py as 'positive_feedback'
        self.last_feedback = ""

    # Data loading
    def load_quiz_pairs(self, source_lang, target_lang, count=5):
        path = os.path.join(os.path.dirname(__file__),'medical_terms.csv')
        pairs=[]
        with open(path,newline='',encoding='utf-8') as f:
            reader=csv.DictReader(f)
            for row in reader:
                src = row.get(f"{self.LANGUAGE_FIELD_MAP[source_lang]}_translation", '').strip()
                tgt = row.get(f"{self.LANGUAGE_FIELD_MAP[target_lang]}_translation", '').strip()
                if src and tgt:
                    pairs.append((src,tgt))
        return random.sample(pairs,min(count,len(pairs)))

    def load_definition_pairs(self, source_lang, target_lang, count=5):
        """Return (word, definition) pairs where 'word' is in source_lang
           and 'definition' is in target_lang."""
        path = os.path.join(os.path.dirname(__file__), 'medical_terms.csv')
        pairs = []

        # map each language key to its definition-column suffix
        definition_field_map = {
            'english':    'english_definition',
            'german':     'german_definition',
            'slovak':     'slovak_definition',
            'spanish':    'spanish_definition',
            'norwegian':  'norwegian_definition',
            'icelandic':  'icelandic_definition',
            'latin':      'definition'        # fallback if ever used
        }

        src_field = f"{self.LANGUAGE_FIELD_MAP[source_lang]}_translation"
        def_field = definition_field_map[target_lang]

        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                src = row.get(src_field, '').strip()
                definition = row.get(def_field, '').strip()
                if src and definition:
                    pairs.append((src, definition))

        return random.sample(pairs, min(count, len(pairs)))

    def load_review_pairs(self):
        # Use personalized review file
        user_files = getattr(self.manager, "user_files", None)
        review_file = user_files["review"] if user_files else None
        pairs = []
        if not review_file or not os.path.exists(review_file):
            return pairs
        with open(review_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                src = row['1st_column'].strip()
                if row['correct_answer_word'].strip():
                    tgt = row['correct_answer_word'].strip()
                else:
                    tgt = row['correct_answer_definition'].strip()
                if src and tgt:
                    pairs.append((src,tgt))
        return pairs

    def start_quiz(self, instance):
        # Validate settings for normal mode: ensure user chose valid options, not defaults
        if not self.review_mode:
            valid_types = {'word+word', 'word+definition'}
            if self.link_type not in valid_types or self.link_source_language not in self.LANGUAGE_FIELD_MAP or self.link_target_language not in self.LANGUAGE_FIELD_MAP:
                self.status_label.text = 'Please, select all options in the Quiz settings.'
                return
        # Clear previous round
        self.word_column_1.clear_widgets()
        self.word_column_2.clear_widgets()
        self.status_label.text = ''
        # Load pairs
        if self.review_mode:
            pairs = self.load_review_pairs()
        else:
            if self.link_type == 'word+word':
                pairs = self.load_quiz_pairs(
                    self.link_source_language,
                    self.link_target_language
                )
            else:  # word+definition
                pairs = self.load_definition_pairs(
                    self.link_source_language,
                    self.link_target_language
                )
        # Populate quiz
        self.source_items = [s for s,_ in pairs]
        self.correct_targets = [t for _,t in pairs]
        self.shuffled_targets = self.correct_targets[:]
        random.shuffle(self.shuffled_targets)
        for s in self.source_items:
            btn = Button(text=s, size_hint_y=None, height=50, font_size=22)  # <-- bigger font
            btn.bind(on_press=self.select_source_word)
            self.word_column_1.add_widget(btn)
        for t in self.shuffled_targets:
            btn = Button(text=t, size_hint_y=None, height=50, font_size=22)  # <-- bigger font
            btn.bind(on_press=self.select_target_word)
            self.word_column_2.add_widget(btn)

    def reset_quiz(self, instance):
        self.score = 0
        self.incorrect = 0
        self.source_items = []
        self.correct_targets = []
        self.selected_source = None
        self.selected_target = None
        self.status_label.text = ''
        self.score_label.text = f'Score: {self.score} | Incorrect: {self.incorrect}'
        self.link_type = None
        self.link_source_language = None
        self.link_target_language = None
        self.review_mode = False
        self.word_column_1.clear_widgets()
        self.word_column_2.clear_widgets()

    def select_source_word(self, instance):
        self.selected_source = instance
        self.check_pair()

    def select_target_word(self, instance):
        self.selected_target = instance
        self.check_pair()

    def check_pair(self):
        if self.selected_source and self.selected_target:
            s_btn, t_btn = self.selected_source, self.selected_target
            idx = self.source_items.index(s_btn.text)
            correct = self.correct_targets[idx]
            if t_btn.text == correct:
                self.score += 1
                s_btn.disabled = t_btn.disabled = True
                s_btn.background_color = t_btn.background_color = (0,1,0,1)
            else:
                self.incorrect += 1
                s_btn.background_color = t_btn.background_color = (1,0,0,1)
                self.log_mistake(s_btn.text, correct, t_btn.text)
                Clock.schedule_once(lambda _: self.reset_button_colors(s_btn, t_btn), 1)
            self.status_label.text = 'Correct!' if t_btn.text == correct else 'Incorrect!'
            self.score_label.text = f'Score: {self.score} | Incorrect: {self.incorrect}'
            self.selected_source = self.selected_target = None
            if all(btn.disabled for btn in self.word_column_1.children):
                # All links finished, show positive feedback before next round
                self.show_positive_feedback()
                self.source_items = []
                # Delay next quiz round until after feedback is shown
                Clock.schedule_once(lambda dt: self.start_quiz(None), 3)

    def show_positive_feedback(self):
        lang = getattr(self.manager, 'language', 'English')
        app_name = getattr(self.manager, "app_name", "The App")
        feedback_list = translations.get(lang, {}).get("positive_feedback", [])
        if feedback_list:
            import random
            feedback = random.choice(feedback_list).format(app_name=app_name)
            self.status_label.text = feedback
        else:
            self.status_label.text = f"Great job in {app_name}!"

    def reset_button_colors(self, s_btn, t_btn):
        # Reset to default Kivy button color
        s_btn.background_color = (1, 1, 1, 1)
        t_btn.background_color = (1, 1, 1, 1)

    def log_mistake(self, src, correct, wrong):
        # Use personalized review file
        user_files = getattr(self.manager, "user_files", None)
        review_file = user_files["review"] if user_files else None
        if not review_file:
            return
        header = ['1st_column','correct_answer_word','wrong_answer_word','correct_answer_definition','wrong_answer_definition']
        file_exists = os.path.isfile(review_file)
        needs_header = True
        if file_exists:
            with open(review_file, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                if first_line.strip().replace(' ', '') == ','.join(header).replace(' ', ''):
                    needs_header = False
        with open(review_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists or needs_header:
                writer.writerow(header)
            writer.writerow([
                src,
                correct if self.link_type=='word+word' else '',
                wrong if self.link_type=='word+word' else '',
                correct if self.link_type!='word+word' else '',
                wrong if self.link_type!='word+word' else ''
            ])

    def open_link_settings(self, instance):
        lang = getattr(self.manager, 'language', 'English')
        t = lambda k: translations[lang].get(k, k)

        # Use explicit translation keys for the quiz type options
        quiz_type_display = {
            t('Word combinations'): 'word+word',
            t('Words and definitions'): 'word+definition'
        }
        quiz_type_reverse = {v: k for k, v in quiz_type_display.items()}

        # Add translations for language names
        language_keys = list(self.LANGUAGE_FIELD_MAP.keys())
        language_display = {
            'english': t('english'),
            'german': t('german'),
            'slovak': t('slovak'),
            'latin': t('latin'),
            'spanish': t('spanish'),
            'norwegian': t('norwegian'),
            'icelandic': t('icelandic')
        }
        language_keys_no_latin = [k for k in language_keys if k != 'latin']

        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        self.link_type_spinner = Spinner(
            text=t('Type of quiz'),
            values=list(quiz_type_display.keys()),
            size_hint=(1, None), height=44
        )
        content.add_widget(self.link_type_spinner)
        self.dynamic_box = BoxLayout(orientation='vertical', spacing=10, size_hint=(1, None))
        content.add_widget(self.dynamic_box)
        btn = Button(text=t("OK"), size_hint=(1, None), height=44)
        content.add_widget(btn)
        self.link_popup = Popup(
            title=t("Quiz Settings"),
            content=content,
            size_hint=(0.8, None), height=300
        )

        def on_type_change(spinner, value):
            self.dynamic_box.clear_widgets()
            mode = quiz_type_display.get(value)
            if not mode:
                return
            # 1st column always all langs
            self.link_source_spinner = Spinner(
                text=t('Select 1st column'),
                values=[language_display[k] for k in language_keys],
                size_hint=(1, None), height=44
            )
            # 2nd column depends on mode
            target_keys = language_keys if mode == 'word+word' else language_keys_no_latin
            self.link_target_spinner = Spinner(
                text=t('Select 2nd column'),
                values=[language_display[k] for k in target_keys],
                size_hint=(1, None), height=44
            )
            self.dynamic_box.add_widget(self.link_source_spinner)
            self.dynamic_box.add_widget(self.link_target_spinner)

        self.link_type_spinner.bind(text=on_type_change)
        btn.bind(on_release=self.apply_link_settings)
        self.link_popup.open()
        self._quiz_type_display = quiz_type_display
        self._language_display = language_display
        self._language_keys = language_keys
        self._language_keys_no_latin = language_keys_no_latin

    def apply_link_settings(self, instance):
        lang = getattr(self.manager, 'language', 'English')
        t = lambda k: translations[lang].get(k, k)
        display_choice = self.link_type_spinner.text
        self.link_type = self._quiz_type_display.get(display_choice)
        def get_key_from_display(display, keys):
            for k in keys:
                if self._language_display[k] == display:
                    return k
            return None
        self.link_source_language = get_key_from_display(self.link_source_spinner.text, self._language_keys)
        if self.link_type == 'word+word':
            self.link_target_language = get_key_from_display(self.link_target_spinner.text, self._language_keys)
        else:
            self.link_target_language = get_key_from_display(self.link_target_spinner.text, self._language_keys_no_latin)
        self.status_label.text = (
            f"{t('Quiz Settings')}: "
            f"{display_choice}, "
            f"{t('Select 1st column')}: {self.link_source_spinner.text} → {t('Select 2nd column')}: {self.link_target_spinner.text}"
        )
        self.link_popup.dismiss()

    def open_review_popup(self, instance):
        lang = getattr(self.manager, 'language', 'English')
        t = lambda k: translations[lang].get(k, k)
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        scroll = ScrollView(size_hint=(1,1))
        list_layout = GridLayout(cols=7, size_hint_y=None, spacing=5)  # 6 data columns + 1 for remove button
        user_files = getattr(self.manager, "user_files", None)
        review_file = user_files["review"] if user_files else None
        path = review_file
        self.review_row_widgets = []
        self.review_row_checks = []
        self.review_row_data = []

        # Header row (no empty cell at start)
        header = [
            t("1st_column"),
            t("correct_answer_word"),
            t("wrong_answer_word"),
            t("correct_answer_definition"),
            t("wrong_answer_definition"),
            "",  # For remove button
        ]
        # Add a checkbox header for selection (optional, can be left blank)
        list_layout.add_widget(Label(text="", size_hint_y=None, height=30))  # Checkbox header
        for h in header:
            list_layout.add_widget(Label(text=h, bold=True, size_hint_y=None, height=30))

        has_rows = False
        if os.path.isfile(path):
            with open(path, newline='', encoding='utf-8') as f:
                try:
                    reader = csv.DictReader(f)
                    expected_keys = {'1st_column', 'correct_answer_word', 'wrong_answer_word', 'correct_answer_definition', 'wrong_answer_definition'}
                    if not reader.fieldnames or not expected_keys.issubset(set(reader.fieldnames)):
                        list_layout.add_widget(Label(
                            text=t('No matching results found.'),
                            size_hint_y=None, height=30))
                    else:
                        for row in reader:
                            has_rows = True
                            self.review_row_data.append(row)
                            cb = CheckBox(active=True, size_hint_x=None, width=30)
                            self.review_row_checks.append(cb)
                            list_layout.add_widget(cb)
                            # Data columns in correct order
                            for key in ["1st_column", "correct_answer_word", "wrong_answer_word", "correct_answer_definition", "wrong_answer_definition"]:
                                val = row.get(key, "")
                                list_layout.add_widget(Label(text=val, size_hint_y=None, height=30))
                            # Remove (X) button in the same row
                            rm_btn = Button(text="✗", size_hint_x=None, width=30, height=30, background_color=(1,0.3,0.3,1))
                            rm_btn.row_data = row
                            rm_btn.row_widget_refs = (cb, list_layout)
                            rm_btn.bind(on_release=self._remove_review_row)
                            list_layout.add_widget(rm_btn)
                            self.review_row_widgets.append((cb, rm_btn))
                        if not has_rows:
                            list_layout.add_widget(Label(
                                text=t('No matching results found.'),
                                size_hint_y=None, height=30))
                        # Set height based on number of rows
                        list_layout.height = max(len(list_layout.children)//7*30, 30)
                except Exception as e:
                    list_layout.add_widget(Label(
                        text=t('Search failed.') + f" ({e})",
                        size_hint_y=None, height=30))
                    list_layout.height = 30
        else:
            list_layout.add_widget(Label(
                text=t('No matching results found.'),
                size_hint_y=None, height=30))
            list_layout.height = 30
        scroll.add_widget(list_layout)
        content.add_widget(scroll)
        btn_row = BoxLayout(orientation='horizontal', size_hint=(1,None), height=50, spacing=20)
        start_btn = Button(text=t('Start Review Quiz'))
        clear_btn = Button(text=t('Clear Review'))
        btn_row.add_widget(start_btn)
        btn_row.add_widget(clear_btn)
        content.add_widget(btn_row)
        self.review_popup = Popup(
            title=t('Review Mistakes'),
            content=content, size_hint=(0.95,0.9))
        start_btn.bind(on_release=self._start_review_quiz_checked)
        clear_btn.bind(on_release=self.confirm_clear_review)
        self.review_popup.open()

    def _remove_review_row(self, btn):
        row = btn.row_data
        # Use personalized review file
        user_files = getattr(self.manager, "user_files", None)
        review_file = user_files["review"] if user_files else None
        path = review_file
        if not path or not os.path.exists(path):
            return  # File does not exist, nothing to remove
        rows = []
        removed = False
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for r in reader:
                if not removed and all(r.get(k, "") == row.get(k, "") for k in fieldnames):
                    removed = True
                    continue
                rows.append(r)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        # Remove from popup UI
        # Each row has 7 widgets: checkbox, 5 labels, remove button
        grid = btn.row_widget_refs[1]
        idx = None
        for i in range(0, len(grid.children), 7):
            if grid.children[i] is btn:
                idx = i
                break
        if idx is not None:
            for _ in range(7):
                grid.remove_widget(grid.children[idx])
        # Optionally, also remove from self.review_row_data and self.review_row_checks

    def _start_review_quiz_checked(self, instance):
        # Only include checked rows in the review quiz
        checked_rows = []
        for cb, rm_btn in self.review_row_widgets:
            if cb.active:
                checked_rows.append(rm_btn.row_data)
        # Save only checked rows to a temp file and load from it
        import tempfile
        import shutil
        if checked_rows:
            temp_path = os.path.join(tempfile.gettempdir(), "review_checked.csv")
            with open(temp_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["1st_column", "correct_answer_word", "wrong_answer_word", "correct_answer_definition", "wrong_answer_definition"])
                writer.writeheader()
                writer.writerows(checked_rows)
            # Monkey-patch load_review_pairs to use temp file for this run
            orig_path = os.path.join(os.path.dirname(__file__), 'review.csv')
            self._orig_review_path = orig_path
            self._review_temp_path = temp_path
            def load_review_pairs_temp():
                pairs = []
                with open(temp_path, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        src = row['1st_column'].strip()
                        if row['correct_answer_word'].strip():
                            tgt = row['correct_answer_word'].strip()
                        else:
                            tgt = row['correct_answer_definition'].strip()
                        if src and tgt:
                            pairs.append((src, tgt))
                return pairs
            self.load_review_pairs = load_review_pairs_temp
        if self.review_popup:
            self.review_popup.dismiss()
        self.review_mode = True
        self.start_quiz(None)

    def go_to_submenu(self, instance):
        # Replace 'submenu' with the actual name of your submenu screen
        self.manager.current = 'submenu'

    def confirm_clear_review(self, instance):
        # Show a confirmation popup before clearing the review.csv file
        lang = getattr(self.manager, 'language', 'English')
        t = lambda k: translations[lang].get(k, k)
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(text=t("Are you sure you want to clear all review mistakes?")))
        btn_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=50, spacing=20)
        yes_btn = Button(text=t("Yes"))
        no_btn = Button(text=t("No"))
        btn_row.add_widget(yes_btn)
        btn_row.add_widget(no_btn)
        content.add_widget(btn_row)
        popup = Popup(title=t("Confirm Clear Review"), content=content, size_hint=(0.6, None), height=200)
        def do_clear(instance):
            path = os.path.join(os.path.dirname(__file__), 'review.csv')
            if os.path.exists(path):
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['1st_column','correct_answer_word','wrong_answer_word','correct_answer_definition','wrong_answer_definition'])
            popup.dismiss()
            if self.review_popup:
                self.review_popup.dismiss()
        yes_btn.bind(on_release=do_clear)
        no_btn.bind(on_release=lambda x: popup.dismiss())
        popup.open()

class MedicalDictionaryApp(App):
    def build(self):
        sm = ScreenManager()
        sm.language = "English"
        sm.selected_search_fields = [
            'latin_translation','genitive',
            'accusative','gender','declination',
            'english_translation','english_definition',
            'german_translation','german_definition',
            'slovak_translation','slovak_definition',
            'spanish_translation','spanish_definition',
            'norwegian_translation','norwegian_definition',
            'icelandic_translation','icelandic_definition'
        ]
        sm.player_name = ""
        sm.app_name = "The App"
        sm.add_widget(MenuScreen(name='menu'))
        sm.add_widget(LoginRegisterScreen(name='login'))
        sm.add_widget(SubMenuScreen(name='submenu'))
        sm.add_widget(SearchScreen(name='search'))
        sm.add_widget(EntryScreen(name='entry'))
        sm.add_widget(QuizScreen(name='quiz'))
        sm.current = 'menu'
        return sm

if __name__ == '__main__':
    MedicalDictionaryApp().run()