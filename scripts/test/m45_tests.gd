extends RefCounted
## M4.5 briefing flow check (validation builds only). Run with
##   --autotest --ui_flow --rv_briefing [--brief_quick] --shots=<dir>
## --ui_flow makes main take the normal start path (briefing / checkpoint
## resume) and lets the menus take input; this script drives them with real
## mouse and keyboard events. Phases survive the two scene reloads in Game meta:
##   A  fresh start: reveal, hover, keyboard focus, loadout round trip, DEPLOY,
##      in-mission review (before and after scripted objective signals),
##      checkpoint saved, RESTART FROM CHECKPOINT
##   B  after the checkpoint reload: no briefing, straight into the mission;
##      RESTART MISSION
##   C  fresh mission again: briefing shown, keyboard DEPLOY
## Objective progress in phase A is scripted (the panels' own `done` signals are
## emitted; nobody walks there) and is logged as such.

var ap
var main
var menus
var br: Briefing
var m: Mission


func _init(autopilot) -> void:
	ap = autopilot
	main = ap.main
	menus = main.menus
	br = menus.briefing
	m = main.mission


func L(s: String) -> void:
	ap.L(s)


func W(t: float) -> void:
	await ap._wait(t)


func check(name: String, ok: bool, detail := "") -> void:
	var res: Array = Game.get_meta("rv_brief_results", [])
	res.append("%s  %s%s" % ["PASS" if ok else "FAIL", name, ("  (" + detail + ")") if detail != "" else ""])
	Game.set_meta("rv_brief_results", res)
	L(res[res.size() - 1])


func until(cond: Callable, timeout: float) -> bool:
	var t := 0.0
	while t < timeout:
		if cond.call():
			return true
		await W(0.05)
		t += 0.05
	return cond.call()


func _center(c: Control) -> Vector2:
	return c.get_screen_transform() * (c.size * 0.5)


func move_to(c: Control) -> void:
	var ev := InputEventMouseMotion.new()
	ev.position = _center(c)
	ev.global_position = ev.position
	Input.parse_input_event(ev)
	await W(0.12)


func click(c: Control) -> void:
	await move_to(c)
	for pressed in [true, false]:
		var ev := InputEventMouseButton.new()
		ev.button_index = MOUSE_BUTTON_LEFT
		ev.pressed = pressed
		ev.position = _center(c)
		ev.global_position = ev.position
		Input.parse_input_event(ev)
		await W(0.06)


## Press and release in the same frame (for buttons that reload the scene:
## nothing may await after the click, the autopilot is freed with the scene).
func click_now(c: Control) -> void:
	var p := _center(c)
	var mv := InputEventMouseMotion.new()
	mv.position = p
	mv.global_position = p
	Input.parse_input_event(mv)
	for pressed in [true, false]:
		var ev := InputEventMouseButton.new()
		ev.button_index = MOUSE_BUTTON_LEFT
		ev.pressed = pressed
		ev.position = p
		ev.global_position = p
		Input.parse_input_event(ev)


func key(k: Key) -> void:
	for pressed in [true, false]:
		var ev := InputEventKey.new()
		ev.keycode = k
		ev.physical_keycode = k
		ev.pressed = pressed
		Input.parse_input_event(ev)
		await W(0.06)


func button(text_prefix: String) -> Button:
	for c in menus.content.get_children():
		if c is Button and c.text.begins_with(text_prefix):
			return c
	return null


func shot(name: String) -> void:
	await ap.shot(name)


func briefing() -> void:
	var phase: String = Game.get_meta("rv_brief_phase", "A")
	L("BRIEFING FLOW phase %s" % phase)
	if phase == "A":
		await _phase_a()
	elif phase == "B":
		await _phase_b()
	else:
		await _phase_c()


func _phase_a() -> void:
	var shown := await until(func(): return menus.screen == "briefing" and br.visible, 30.0)
	check("briefing opens on a new mission", shown, "screen=%s" % menus.screen)
	check("mission waits in BRIEFING while the briefing is up", Game.state == Game.State.BRIEFING and get_tree_paused())
	await W(0.45)
	await shot("b01_reveal_in_progress")
	await W(2.4)
	await shot("b02_briefing_full")
	var plan := BriefingIntel.plan(main.level)
	L("plan from level collision: %d walls, %d machinery, %d low cover, %d gallery slabs" % [plan.walls.size(), plan.solids.size(), plan.low.size(), plan.galleries.size()])
	L("markers: %s" % ", ".join(br.intel.markers.map(func(x): return "%s@%s" % [x.id, BriefingIntel.grid_ref(x.pos)])))
	check("map built from level geometry", plan.walls.size() > 100 and plan.solids.size() > 20, "%d walls" % plan.walls.size())
	check("objective markers placed from mission objects", br.intel.markers.size() >= 10)
	var est := 0
	for r in br.intel.counts:
		est += br.intel.counts[r][0] + br.intel.counts[r][1]
	check("threat estimate matches the start roster", est == Mission.START_SET.size(), "%d units" % est)
	if "--brief_quick" in OS.get_cmdline_user_args():
		return
	# Mouse hover: a task row lights its markers on the map.
	await move_to(br._rows["02"])
	await W(0.3)
	await shot("b03_hover_task02_map_highlight")
	check("hovering task 02 highlights the breakers on the map", br._map.highlight == "02")
	# Keyboard: Up from DEPLOY walks the rows.
	await move_to(br._top)   # neutral spot, clears the hover
	br._deploy.grab_focus()
	await W(0.1)
	for i in 4:
		await key(KEY_UP)
	await W(0.25)
	var fo: Control = br.get_viewport().gui_get_focus_owner()
	await shot("b04_keyboard_focus_task03")
	check("arrow keys move focus through the tasking", fo is Briefing.ObjRow, "focus=%s map=%s" % [fo.get("id") if fo else "none", br._map.highlight])
	# Loadout round trip from the briefing.
	await click(br._side_buttons.get_child(0))
	await W(0.4)
	check("LOADOUT opens from the briefing", menus.screen == "loadout" and not br.visible)
	await shot("b05_loadout_from_briefing")
	var back := button("BACK")
	if back:
		await click(back)
	await W(0.5)
	check("BACK returns to the briefing", menus.screen == "briefing" and br.visible)
	# DEPLOY with the mouse.
	await move_to(br._deploy)
	await W(0.2)
	await click(br._deploy)
	await W(0.35)
	await shot("b06_deploy_authorising")
	check("DEPLOY does not start the mission before the cut", Game.state == Game.State.BRIEFING)
	await until(func(): return br._card.visible and br._card.modulate.a > 0.9, 4.0)
	await shot("b07_title_card")
	check("mission still waiting during the title card", Game.state == Game.State.BRIEFING)
	var gone := await until(func(): return not br.visible, 6.0)
	await W(0.2)
	await shot("b08_in_game_after_deploy")
	check("gameplay starts after the transition", gone and Game.state == Game.State.INFILTRATE and m.stage == "infiltrate" and not get_tree_paused(),
		"state=%d stage=%s" % [Game.state, m.stage])
	check("first objective set by the mission", Game.objective_text.begins_with("RELEASE LOCKDOWN"), Game.objective_text)
	check("mouse captured for play", Input.mouse_mode == Input.MOUSE_MODE_CAPTURED)
	await W(1.0)
	# Review from the pause menu.
	await key(KEY_ESCAPE)
	await W(0.3)
	check("ESC opens the pause menu", menus.screen == "pause")
	var mb := button("MISSION BRIEFING")
	check("pause menu offers MISSION BRIEFING", mb != null)
	if mb:
		await click(mb)
	await W(0.8)
	check("briefing review opens from pause", menus.screen == "briefing_review" and br.visible and br.mode == "review" and not br._deploy.visible)
	await shot("b09_review_at_start")
	await key(KEY_ESCAPE)
	await W(0.2)
	await key(KEY_ESCAPE)
	await W(0.3)
	check("ESC backs out to the game", menus.screen == "" and Game.is_active())
	L("SCRIPTED: lockdown panel and breaker A `done` signals emitted (no walking)")
	m.ex.lockdown_panel.done.emit()
	m.ex.breakers[0].done.emit()
	await W(1.5)
	await key(KEY_ESCAPE)
	await W(0.3)
	mb = button("MISSION BRIEFING")
	if mb:
		await click(mb)
	await W(0.8)
	await shot("b10_review_progress")
	var d5_open := false
	for d in br.intel.doors:
		if d.id == "D5":
			d5_open = not d.sealed
	check("review shows live progress", m.flags.lockdown and m.flags.power == 1 and d5_open and br._rows.has("01"))
	await click(br._return)
	await W(0.3)
	check("RETURN goes back to the pause menu", menus.screen == "pause")
	await key(KEY_ESCAPE)
	await W(0.3)
	# Checkpoint, then restart from it.
	m.save_checkpoint("briefing test", main.player.global_transform)
	check("checkpoint saved", Game.checkpoint.get("name", "") == "briefing test")
	await key(KEY_ESCAPE)
	await W(0.3)
	var rc := button("RESTART FROM CHECKPOINT")
	check("pause menu offers RESTART FROM CHECKPOINT", rc != null)
	Game.set_meta("rv_brief_phase", "B")
	Game.set_meta("rv_reload_pending", true)
	ap._write_log_named("briefing_log_A.txt")
	if rc:
		click_now(rc)   # the scene reloads; this autopilot is freed with it


func _phase_b() -> void:
	await W(3.0)
	check("checkpoint respawn skips the briefing", menus.screen == "" and not br.visible and Game.is_active(), "screen=%s" % menus.screen)
	check("checkpoint state restored", m.flags.lockdown and m.flags.power == 1 and m.stage == "infiltrate")
	await shot("b11_checkpoint_respawn_no_briefing")
	await key(KEY_ESCAPE)
	await W(0.3)
	var rm := button("RESTART MISSION")
	check("pause menu offers RESTART MISSION", rm != null)
	Game.set_meta("rv_brief_phase", "C")
	Game.set_meta("rv_reload_pending", true)
	ap._write_log_named("briefing_log_B.txt")
	if rm:
		click_now(rm)


func _phase_c() -> void:
	var shown := await until(func(): return menus.screen == "briefing" and br.visible, 30.0)
	check("RESTART MISSION shows the briefing again", shown and Game.state == Game.State.BRIEFING and Game.checkpoint.is_empty() and not m.flags.lockdown)
	await W(0.6)
	await shot("b12_restart_mission_briefing")
	await key(KEY_ENTER)
	var gone := await until(func(): return not br.visible, 7.0)
	await W(0.2)
	check("ENTER deploys", gone and Game.state == Game.State.INFILTRATE and m.stage == "infiltrate")
	await shot("b13_keyboard_deploy_in_game")
	var res: Array = Game.get_meta("rv_brief_results", [])
	var fails := res.filter(func(s): return s.begins_with("FAIL")).size()
	L("BRIEFING FLOW RESULT: %d checks, %d failed" % [res.size(), fails])
	var f := FileAccess.open(ap.out_dir.path_join("briefing_results.txt"), FileAccess.WRITE)
	f.store_string("\n".join(res) + "\n%d checks, %d failed\n" % [res.size(), fails])
	f.close()


func get_tree_paused() -> bool:
	return main.get_tree().paused
