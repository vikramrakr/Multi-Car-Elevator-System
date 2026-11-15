import tkinter as tk

# =========================================================
# 1. BACKEND LOGIC (Modular Elevator Classes)
# =========================================================

class CarButton:
    def __init__(self, button_type, floor_number=None):
        self.button_type = button_type  # "FLOOR", "DOOR_OPEN", "DOOR_CLOSE"
        self.floor_number = floor_number
        self.is_illuminated = False

    def press(self, elevator_car):
        if not self.is_illuminated:
            self.is_illuminated = True
            if self.button_type == "FLOOR":
                elevator_car.request_destination(self.floor_number)
            elif self.button_type == "DOOR_OPEN":
                elevator_car.press_door_open()
                self.is_illuminated = False
            elif self.button_type == "DOOR_CLOSE":
                elevator_car.press_door_close()
                self.is_illuminated = False

    def clear(self):
        self.is_illuminated = False


class CarOperatingPanel:
    def __init__(self, total_floors, elevator_car):
        self.elevator_car = elevator_car
        self.buttons = {}
        for floor in range(1, total_floors + 1):
            self.buttons[f"FLOOR_{floor}"] = CarButton("FLOOR", floor_number=floor)
        self.buttons["DOOR_OPEN"] = CarButton("DOOR_OPEN")
        self.buttons["DOOR_CLOSE"] = CarButton("DOOR_CLOSE")

    def press_floor(self, floor):
        key = f"FLOOR_{floor}"
        if key in self.buttons:
            self.buttons[key].press(self.elevator_car)

    def clear_floor(self, floor):
        key = f"FLOOR_{floor}"
        if key in self.buttons:
            self.buttons[key].clear()


class HallButton:
    def __init__(self, floor_number, direction):
        self.floor_number = floor_number
        self.direction = direction
        self.is_illuminated = False

    def press(self, elevator_system):
        if not self.is_illuminated:
            self.is_illuminated = True
            elevator_system.request_pickup(self.floor_number, self.direction)

    def clear(self):
        self.is_illuminated = False


class HallCallPanel:
    def __init__(self, floor_number, total_floors, elevator_system):
        self.floor_number = floor_number
        self.elevator_system = elevator_system
        self.buttons = {}
        if floor_number < total_floors:
            self.buttons["UP"] = HallButton(floor_number, "UP")
        if floor_number > 1:
            self.buttons["DOWN"] = HallButton(floor_number, "DOWN")

    def press_button(self, direction):
        if direction in self.buttons:
            self.buttons[direction].press(self.elevator_system)

    def clear_button(self, direction):
        if direction in self.buttons:
            self.buttons[direction].clear()


class ElevatorCar:
    def __init__(self, car_id, total_floors, system, dwell_seconds=2.0, travel_speed=1.0):
        self.car_id = car_id
        self.total_floors = total_floors
        self.system = system

        self.current_floor = 1
        self.visual_floor = 1.0  # Smooth float position for UI animation
        self.target_floor = None
        self.direction = "IDLE"
        self.motion_state = "STOPPED"

        self.door_state = "CLOSED"
        self.dwell_seconds = dwell_seconds
        self.travel_speed = travel_speed
        self.door_obstructed = False

        self.up_queue = []
        self.down_queue = []
        self.panel = CarOperatingPanel(total_floors, self)

        # Non-blocking timer for UI step updates
        self.action_timer = 0.0

    def report(self):
        return {
            "car_id": self.car_id,
            "current_floor": self.current_floor,
            "visual_floor": self.visual_floor,
            "target_floor": self.target_floor,
            "direction": self.direction,
            "motion_state": self.motion_state,
            "door_state": self.door_state,
            "workload": len(self.up_queue) + len(self.down_queue),
            "up_queue": list(self.up_queue),
            "down_queue": list(self.down_queue),
        }

    def step(self, dt):
        """Advances car state by dt seconds (called by GUI loop)."""
        # 1. Handle dwelling with doors open
        if self.door_state == "OPEN":
            if self.door_obstructed:
                return  # Stay open while obstructed
            self.action_timer -= dt
            if self.action_timer <= 0:
                self.close_doors()
            return

        # 2. Pick next destination if idle/stopped
        if self.motion_state == "STOPPED" and self.target_floor is None:
            self._dispatch_next()
            return

        # 3. Move smoothly toward target_floor
        if self.target_floor is not None:
            step_dir = 1 if self.target_floor > self.visual_floor else -1
            move_amount = (dt / self.travel_speed) * step_dir
            self.visual_floor += move_amount
            self.current_floor = round(self.visual_floor)

            remaining = abs(self.target_floor - self.visual_floor)
            if remaining <= 1.0 and self.motion_state == "CRUISING":
                self.motion_state = "DECELERATING"

            # Check if arrived at target floor
            if (step_dir == 1 and self.visual_floor >= self.target_floor) or (
                step_dir == -1 and self.visual_floor <= self.target_floor
            ):
                self.visual_floor = float(self.target_floor)
                self.current_floor = self.target_floor
                self.motion_state = "STOPPED"
                arrived_floor = self.current_floor
                self.target_floor = None

                self.panel.clear_floor(arrived_floor)
                self.open_doors()
                self.action_timer = self.dwell_seconds
                self.system.on_floor_serviced(self, arrived_floor)

    def _dispatch_next(self):
        next_floor = None
        if self.direction == "UP":
            if self.up_queue:
                next_floor = self.up_queue.pop(0)
            elif self.down_queue:
                self.direction = "DOWN"
                next_floor = self.down_queue.pop(0)
            else:
                self.direction = "IDLE"
        elif self.direction == "DOWN":
            if self.down_queue:
                next_floor = self.down_queue.pop(0)
            elif self.up_queue:
                self.direction = "UP"
                next_floor = self.up_queue.pop(0)
            else:
                self.direction = "IDLE"
        elif self.direction == "IDLE":
            if self.up_queue:
                self.direction = "UP"
                next_floor = self.up_queue.pop(0)
            elif self.down_queue:
                self.direction = "DOWN"
                next_floor = self.down_queue.pop(0)

        if next_floor is not None:
            if next_floor == self.current_floor:
                self.panel.clear_floor(next_floor)
                self.open_doors()
                self.action_timer = self.dwell_seconds
                self.system.on_floor_serviced(self, next_floor)
            else:
                self.target_floor = next_floor
                self.direction = "UP" if next_floor > self.current_floor else "DOWN"
                dist = abs(next_floor - self.current_floor)
                self.motion_state = "CRUISING" if dist > 1 else "ACCELERATING"

    def add_stop(self, floor, direction):
        if direction == "UP":
            self._add_up(floor)
        elif direction == "DOWN":
            self._add_down(floor)

    def request_destination(self, floor):
        if floor == self.current_floor and self.motion_state == "STOPPED":
            self.panel.clear_floor(floor)
            self.open_doors()
            self.action_timer = self.dwell_seconds
            return

        if self.direction == "UP":
            self._add_up(floor) if floor > self.current_floor else self._add_down(floor)
        elif self.direction == "DOWN":
            self._add_down(floor) if floor < self.current_floor else self._add_up(floor)
        else:
            if floor > self.current_floor:
                self.direction = "UP"
                self._add_up(floor)
            else:
                self.direction = "DOWN"
                self._add_down(floor)

    def _add_up(self, floor):
        if floor not in self.up_queue:
            self.up_queue.append(floor)
            self.up_queue.sort()

    def _add_down(self, floor):
        if floor not in self.down_queue:
            self.down_queue.append(floor)
            self.down_queue.sort(reverse=True)

    def open_doors(self):
        if self.motion_state == "STOPPED":
            self.door_state = "OPEN"

    def close_doors(self):
        if self.door_obstructed:
            self.open_doors()
            return False
        self.door_state = "CLOSED"
        return True

    def trigger_obstruction(self, obstructed):
        self.door_obstructed = obstructed
        if obstructed and self.motion_state == "STOPPED":
            self.open_doors()

    def press_door_open(self):
        if self.motion_state == "STOPPED":
            self.open_doors()
            self.action_timer = self.dwell_seconds

    def press_door_close(self):
        if self.motion_state == "STOPPED" and self.door_state == "OPEN":
            self.close_doors()


class ElevatorSystem:
    def __init__(self, num_floors, num_elevators):
        self.num_floors = num_floors
        self.num_elevators = num_elevators
        self.elevators = [
            ElevatorCar(car_id=i + 1, total_floors=num_floors, system=self)
            for i in range(num_elevators)
        ]
        self.hall_panels = {
            floor: HallCallPanel(floor, num_floors, self)
            for floor in range(1, num_floors + 1)
        }

    def step(self, dt):
        for car in self.elevators:
            car.step(dt)

    def request_pickup(self, floor, direction):
        reports = [car.report() for car in self.elevators]
        best_car = self._select_best_car(reports, floor, direction)
        best_car.add_stop(floor, direction)

    def _select_best_car(self, reports, target_floor, call_dir):
        candidates = []
        for report in reports:
            car = self.elevators[report["car_id"] - 1]
            c_floor = report["current_floor"]
            c_dir = report["direction"]

            on_the_way = (
                (c_dir == "UP" and call_dir == "UP" and target_floor > c_floor)
                or (c_dir == "DOWN" and call_dir == "DOWN" and target_floor < c_floor)
                or (c_dir == "IDLE")
            )
            if on_the_way:
                candidates.append((abs(target_floor - c_floor), report["workload"], car))

        if not candidates:
            for report in reports:
                car = self.elevators[report["car_id"] - 1]
                candidates.append((abs(target_floor - report["current_floor"]), report["workload"], car))

        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][2]

    def on_floor_serviced(self, car, floor):
        if floor in self.hall_panels:
            self.hall_panels[floor].clear_button("UP")
            self.hall_panels[floor].clear_button("DOWN")


# =========================================================
# 2. TKINTER FRONTEND (Visual Dashboard)
# =========================================================

class ElevatorGUI:
    def __init__(self, root, num_floors, num_elevators):
        self.root = root
        self.root.title("Multi Car Elevator System")
        self.root.configure(bg="#1e1e2e")

        self.num_floors = num_floors
        self.num_elevators = num_elevators
        self.system = ElevatorSystem(num_floors, num_elevators)

        # Auto-scale height so tall buildings stay visible
        self.floor_height = max(32, min(65, 650 // num_floors))
        self.shaft_width = max(75, min(110, 700 // num_elevators))
        self.canvas_height = self.num_floors * self.floor_height + 40
        self.canvas_width = self.num_elevators * self.shaft_width + 40

        self.hall_btn_widgets = {}
        self.car_btn_widgets = {}
        self.car_status_labels = {}

        self._build_layout()
        self._update_loop()

    def _create_scrollable_container(self, parent, width):
        """Creates a guaranteed-visible vertical scrollable frame."""
        # 1. Pack scrollbar FIRST so it is never pushed off-screen
        scrollbar = tk.Scrollbar(parent, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 2. Create canvas linked to the scrollbar
        canvas = tk.Canvas(
            parent, width=width, bg="#2a2a3c", highlightthickness=0,
            yscrollcommand=scrollbar.set
        )
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)

        scrollable_frame = tk.Frame(canvas, bg="#2a2a3c")
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig(window_id, width=event.width)

        scrollable_frame.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Cross-platform mouse-wheel scrolling
        def _scroll(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            elif event.delta:
                step = -1 if event.delta > 0 else 1
                canvas.yview_scroll(step, "units")

        def _bind_wheel_to_children(widget):
            widget.bind("<MouseWheel>", _scroll)
            widget.bind("<Button-4>", _scroll)
            widget.bind("<Button-5>", _scroll)
            for child in widget.winfo_children():
                _bind_wheel_to_children(child)

        self.root.after(150, lambda: _bind_wheel_to_children(parent))
        return scrollable_frame

    def _build_layout(self):
        main_frame = tk.Frame(self.root, bg="#1e1e2e", padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- LEFT: Hall Call Panels (Scrollable) ---
        hall_outer = tk.LabelFrame(
            main_frame, text="Hall Call Panels", fg="white", bg="#2a2a3c", padx=8, pady=8
        )
        hall_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        hall_frame = self._create_scrollable_container(hall_outer, width=190)

        for floor in range(self.num_floors, 0, -1):
            row = tk.Frame(hall_frame, bg="#2a2a3c")
            row.pack(fill=tk.X, pady=3)

            tk.Label(
                row, text=f"Floor {floor}", width=8, fg="#cdd6f4", bg="#2a2a3c", font=("Arial", 10, "bold")
            ).pack(side=tk.LEFT)

            panel = self.system.hall_panels[floor]
            self.hall_btn_widgets[floor] = {}

            if "UP" in panel.buttons:
                btn_up = tk.Button(
                    row, text="▲ UP", width=6,
                    command=lambda f=floor: self.system.hall_panels[f].press_button("UP")
                )
                btn_up.pack(side=tk.LEFT, padx=2)
                self.hall_btn_widgets[floor]["UP"] = btn_up

            if "DOWN" in panel.buttons:
                btn_dn = tk.Button(
                    row, text="▼ DN", width=6,
                    command=lambda f=floor: self.system.hall_panels[f].press_button("DOWN")
                )
                btn_dn.pack(side=tk.LEFT, padx=2)
                self.hall_btn_widgets[floor]["DOWN"] = btn_dn

        # --- CENTER: Elevator Shafts Canvas ---
        shaft_frame = tk.LabelFrame(
            main_frame, text="Elevator Shafts", fg="white", bg="#2a2a3c", padx=10, pady=10
        )
        shaft_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 15))

        self.canvas = tk.Canvas(
            shaft_frame, width=self.canvas_width, height=self.canvas_height, bg="#181825", highlightthickness=0
        )
        self.canvas.pack()

# --- RIGHT: Car Operating Panels (Single Vertical Stack + Scrollbar) ---
        cars_outer = tk.LabelFrame(
            main_frame, text="Car Operating Panels", fg="white", bg="#2a2a3c", padx=8, pady=8
        )
        cars_outer.pack(side=tk.LEFT, fill=tk.Y)

        cars_frame = self._create_scrollable_container(cars_outer, width=280)

        for car in self.system.elevators:
            cid = car.car_id
            c_box = tk.LabelFrame(
                cars_frame, text=f"Car {cid}", fg="#89b4fa", bg="#313244", padx=8, pady=8
            )
            c_box.pack(fill=tk.X, padx=4, pady=6)

            status_lbl = tk.Label(
                c_box, text="Floor 1 | IDLE | CLOSED", fg="#a6adc8", bg="#313244", font=("Arial", 8)
            )
            status_lbl.pack(anchor="w", pady=(0, 5))
            self.car_status_labels[cid] = status_lbl

            # Floor buttons grid
            btn_grid = tk.Frame(c_box, bg="#313244")
            btn_grid.pack()
            self.car_btn_widgets[cid] = {}

            for f in range(1, self.num_floors + 1):
                b = tk.Button(
                    btn_grid, text=str(f), width=3,
                    command=lambda c=car, fl=f: c.panel.press_floor(fl)
                )
                b.grid(row=(f - 1) // 5, column=(f - 1) % 5, padx=2, pady=2)
                self.car_btn_widgets[cid][f] = b

            # Door & Obstruction Controls
            ctrl_row = tk.Frame(c_box, bg="#313244")
            ctrl_row.pack(pady=(6, 0))

            tk.Button(ctrl_row, text="◄|► Open", command=car.press_door_open).pack(side=tk.LEFT, padx=2)
            tk.Button(ctrl_row, text="►|◄ Close", command=car.press_door_close).pack(side=tk.LEFT, padx=2)

            obs_var = tk.BooleanVar(value=False)
            tk.Checkbutton(
                ctrl_row, text="Block", variable=obs_var, bg="#313244", fg="#f38ba8",
                selectcolor="#1e1e2e", command=lambda c=car, v=obs_var: c.trigger_obstruction(v.get())
            ).pack(side=tk.LEFT, padx=4)

    def _draw_shafts(self):
        self.canvas.delete("all")

        for f in range(1, self.num_floors + 1):
            y = self.canvas_height - (f * self.floor_height) + 15
            self.canvas.create_line(10, y, self.canvas_width - 10, y, fill="#313244", dash=(4, 4))
            self.canvas.create_text(20, y - 10, text=f"F{f}", fill="#6c7086", font=("Arial", 8))

        for idx, car in enumerate(self.system.elevators):
            rep = car.report()
            x_center = 75 + idx * self.shaft_width
            half_w = min(25, (self.shaft_width // 2) - 10)

            self.canvas.create_rectangle(
                x_center - half_w - 4, 15, x_center + half_w + 4, self.canvas_height - 15, outline="#45475a"
            )

            y_bottom = self.canvas_height - (rep["visual_floor"] * self.floor_height) + 15
            y_top = y_bottom - (self.floor_height - 8)

            if rep["door_state"] == "OPEN":
                fill_color = "#a6e3a1"
            elif rep["motion_state"] != "STOPPED":
                fill_color = "#89b4fa"
            else:
                fill_color = "#bac2de"

            self.canvas.create_rectangle(
                x_center - half_w, y_top, x_center + half_w, y_bottom, fill=fill_color, outline="white", width=2
            )
            self.canvas.create_text(
                x_center, (y_top + y_bottom) / 2,
                text=f"C{car.car_id}\n{rep['door_state']}",
                fill="#11111b", font=("Arial", 7, "bold")
            )

    def _sync_buttons_and_labels(self):
        for floor, panel in self.system.hall_panels.items():
            for direction, btn_obj in panel.buttons.items():
                widget = self.hall_btn_widgets[floor][direction]
                widget.configure(bg="#f9e2af" if btn_obj.is_illuminated else "#e0e0e0")

        for car in self.system.elevators:
            rep = car.report()
            self.car_status_labels[car.car_id].configure(
                text=f"F{rep['current_floor']} | {rep['direction']} | {rep['motion_state']}"
            )
            for f in range(1, self.num_floors + 1):
                btn_obj = car.panel.buttons[f"FLOOR_{f}"]
                widget = self.car_btn_widgets[car.car_id][f]
                widget.configure(bg="#f9e2af" if btn_obj.is_illuminated else "#e0e0e0")

    def _update_loop(self):
        self.system.step(0.05)
        self._draw_shafts()
        self._sync_buttons_and_labels()
        self.root.after(50, self._update_loop)

# =========================================================
# 3. STARTUP VALIDATION & LAUNCH
# =========================================================

def get_simulation_config():
    print("=" * 50)
    print("Welcome to the Multi Car Elevator System!")
    print("=" * 50)

    # Validate number of floors (m): must be >= 2
    while True:
        try:
            m = int(input("How many floors do you want (minimum 2)? "))
            if m >= 2:
                break
            print("Ineligible input: You need at least 2 floors. Try again.\n")
        except ValueError:
            print("Ineligible input: Please enter a valid whole number. Try again.\n")

    # Validate number of lifts (n): must be >= 1
    while True:
        try:
            n = int(input("How many lifts do you want (minimum 1)? "))
            if n >= 1:
                break
            print("Ineligible input: You need at least 1 lift. Try again.\n")
        except ValueError:
            print("Ineligible input: Please enter a valid whole number. Try again.\n")

    print(f"\nConfiguration accepted! Launching simulation with {m} floors and {n} lifts...")
    return m, n


if __name__ == "__main__":
    m, n = get_simulation_config()

    root = tk.Tk()
    app = ElevatorGUI(root, num_floors=m, num_elevators=n)
    root.mainloop()