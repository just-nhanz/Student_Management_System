from tkinter import messagebox, ttk

from app.gui.components.widgets import DataTable, FormFields, acting_user, confirm, run
from app.services.auth_service import AuthService

STAFF_ROLES = ["SYSTEM_ADMIN", "TRAINING_MANAGER", "FINANCE_MANAGER"]
ALL_ROLES = STAFF_ROLES + ["LECTURER", "STUDENT"]


class LoginView(ttk.Frame):
    """UC01: man hinh dang nhap."""

    def __init__(self, parent, on_success):
        super().__init__(parent, padding=30)
        self.on_success = on_success
        ttk.Label(self, text="Student Management System", font=("Arial", 16, "bold")).grid(columnspan=2, pady=10)
        ttk.Label(self, text="Username").grid(row=1, column=0, sticky="e", pady=4)
        ttk.Label(self, text="Password").grid(row=2, column=0, sticky="e", pady=4)
        self.username = ttk.Entry(self, width=28)
        self.password = ttk.Entry(self, width=28, show="*")
        self.username.grid(row=1, column=1, pady=4)
        self.password.grid(row=2, column=1, pady=4)
        ttk.Button(self, text="Login", command=self.login).grid(row=3, columnspan=2, pady=10)
        self.password.bind("<Return>", lambda event: self.login())
        self.username.bind("<Return>", lambda event: self.password.focus_set())
        self.username.focus_set()

    def login(self):
        user, failed = run(lambda: AuthService().login(self.username.get(), self.password.get()))
        if not failed:
            self.on_success(user)


class ChangePasswordView(ttk.Frame):
    """UC03: doi mat khau (cung dung khi must_change_password = 1)."""

    def __init__(self, parent, user, on_done=None):
        super().__init__(parent, padding=20)
        self.user = acting_user(user)
        self.on_done = on_done
        self.entries = {}
        labels = [("current", "Current password"), ("new", "New password"), ("confirm", "Confirm new password")]
        for index, (key, label) in enumerate(labels):
            ttk.Label(self, text=label).grid(row=index, column=0, sticky="e", pady=4)
            entry = ttk.Entry(self, width=28, show="*")
            entry.grid(row=index, column=1, pady=4)
            self.entries[key] = entry
        ttk.Button(self, text="Save", command=self.save).grid(row=3, columnspan=2, pady=8)

    def save(self):
        _, failed = run(lambda: AuthService().change_password(
            self.user, self.entries["current"].get(), self.entries["new"].get(),
            self.entries["confirm"].get()), "Password changed successfully.")
        if not failed and self.on_done:
            self.on_done()


class AccountAdminView(ttk.Frame):
    """UC04: quan ly tai khoan (System Administrator)."""

    def __init__(self, parent, user):
        super().__init__(parent, padding=10)
        self.user = acting_user(user)
        self.service = AuthService()
        self.table = DataTable(self, ("account_id", "username", "full_name", "email", "phone_number", "status", "roles"))
        self.table.pack(fill="both", expand=True)
        self.table.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.form = FormFields(self, [
            ("username", "Username"), ("full_name", "Full name"), ("email", "E-mail"),
            ("phone_number", "Phone"), ("role", "Role (for Create)", STAFF_ROLES),
            ("roles", "Roles for 'Set roles' (comma-separated)"), ("reason", "Reason (Lock / Unlock)")])
        self.form.pack(pady=6)
        buttons = ttk.Frame(self)
        buttons.pack()
        for text, command in [("Create", self.create), ("Lock", self.lock), ("Unlock", self.unlock),
                              ("Reset password", self.reset), ("Set roles", self.set_roles),
                              ("Refresh", self.refresh)]:
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=4)
        self.refresh()

    def refresh(self):
        rows, failed = run(lambda: self.service.list_accounts(self.user))
        if not failed:
            for row in rows:
                row["roles"] = ", ".join(row["roles"])
            self.table.load(rows)

    def on_select(self, _event):
        row = self.table.selected()
        if row is not None:
            self.form.set(row)

    def _selected_id(self):
        row = self.table.selected()
        if row is None:
            messagebox.showinfo("Select", "Please select an account in the table.")
            return None
        return row["account_id"]

    def create(self):
        data = self.form.get()
        roles = [data["role"]] if data["role"] else []
        result, failed = run(lambda: self.service.create_account(
            self.user, data["username"], data["full_name"], data["email"], data["phone_number"], roles))
        if not failed:
            messagebox.showinfo("Account created", "Temporary password (shown once): %s" % result["temporary_password"])
            self.refresh()

    def lock(self):
        account_id = self._selected_id()
        if account_id is not None and confirm("Lock this account?"):
            run(lambda: self.service.lock_account(self.user, account_id, self.form.get()["reason"]), "Account locked.")
            self.refresh()

    def unlock(self):
        account_id = self._selected_id()
        if account_id is not None and confirm("Unlock this account?"):
            run(lambda: self.service.unlock_account(self.user, account_id, self.form.get()["reason"]),
                "Account unlocked.")
            self.refresh()

    def reset(self):
        account_id = self._selected_id()
        if account_id is not None and confirm("Reset the password of this account?"):
            password, failed = run(lambda: self.service.reset_password(self.user, account_id))
            if not failed:
                messagebox.showinfo("Password reset", "Temporary password (shown once): %s" % password)

    def set_roles(self):
        account_id = self._selected_id()
        if account_id is None:
            return
        names = []
        for part in self.form.get()["roles"].split(","):
            if part.strip() != "":
                names.append(part.strip())
        if confirm("Set roles %s for this account?" % ", ".join(names)):
            run(lambda: self.service.assign_roles(self.user, account_id, names), "Roles updated.")
            self.refresh()