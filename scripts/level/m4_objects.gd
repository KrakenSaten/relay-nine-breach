class_name M4Objects
extends RefCounted
## M4 interactive mission objects (instantiated by Expansion).


## Generic hold-to-use station (terminal, lift call panel, valve...).
class HoldStation extends StaticBody3D:
	signal done
	var prompt := "[HOLD F] USE"
	var hold_time := 1.5
	var active := true            # false -> no prompt (wrong mission stage)
	var locked_text := ""         # shown instead of the prompt when blocked
	var blocked := false
	var once := true
	var _progress := 0.0
	var _tick := 0.0
	var _done := false

	func _ready() -> void:
		collision_layer = 1
		collision_mask = 0
		set_meta("surface", "metal")

	func get_prompt(_p: Node) -> String:
		if not active or (_done and once):
			return ""
		if blocked:
			return locked_text
		return prompt

	func hold(_p: Node, delta: float) -> float:
		if not active or blocked or (_done and once):
			return 0.0
		if delta < 0.0:
			_progress = 0.0
			return 0.0
		_progress += delta
		_tick -= delta
		if _tick <= 0.0:
			_tick = 0.25
			Sfx.play("ui_hack_tick", -9.0)
		if _progress >= hold_time:
			_progress = 0.0
			_done = true
			Sfx.play("ui_hack_done", -4.0)
			done.emit()
			return 1.0
		return _progress / hold_time

	func reset_done() -> void:
		_done = false


## Main breaker: a hold station that throws a lever and lights lamps.
class BreakerLever extends HoldStation:
	var lever: Node3D
	var lamp_on: Node3D
	var lamp_off: Node3D
	var thrown := false
	var _a := 0.0

	func throw_now(instant := false) -> void:
		thrown = true
		_done = true
		if instant:
			_a = 1.0
		if lamp_on: lamp_on.visible = true
		if lamp_off: lamp_off.visible = false

	func _process(dt: float) -> void:
		if thrown and _a < 1.0:
			_a = minf(1.0, _a + dt * 4.0)
			if _a >= 1.0:
				Fx.mini_arcs(global_position + Vector3.UP * 0.2, 4, 0.4)
		if lever:
			lever.rotation.x = deg_to_rad(lerpf(-45.0, 45.0, _a))


## Destructible capacitor stack (shoot it).
class CapacitorStack extends StaticBody3D:
	signal destroyed
	var hp := 420.0
	var dead := false
	var intact: Node3D
	var broken: Node3D
	var glow: OmniLight3D

	func _ready() -> void:
		collision_layer = 1
		collision_mask = 0
		set_meta("surface", "metal")

	func get_prompt(_p: Node) -> String:
		return "" if dead else "CAPACITOR STACK - DESTROY IT"

	func take_hit(dmg: float, pos: Vector3, _dir: Vector3, normal: Vector3) -> void:
		if dead:
			Fx.impact(pos, normal, "metal")
			return
		Fx.impact(pos, normal, "weak")
		Sfx.play_3d("capacitor_hit" if ResourceLoader.exists("res://assets/audio/capacitor_hit_0.wav") else "robot_weakpoint", pos, 0.0, 0.08, 6.0)
		hp -= dmg
		if glow:
			glow.light_energy = 2.0 + randf() * 3.0
		if hp <= 0.0:
			destroy()

	func destroy(silent := false) -> void:
		if dead:
			return
		dead = true
		if intact: intact.visible = false
		if broken: broken.visible = true
		if glow: glow.visible = false
		if silent:
			return   # checkpoint restore: state only, no events
		var c := global_position + Vector3.UP * 1.3
		Fx.overload(c)
		Sfx.play_3d("capacitor_destroyed" if ResourceLoader.exists("res://assets/audio/capacitor_destroyed.wav") else "robot_death", c, 4.0, 0.0, 12.0)
		Game.emit_noise(c, 30.0, Game.player)
		destroyed.emit()


## Sliding blast door (opens once, scripted).
class BlastDoor extends Node3D:
	var body: AnimatableBody3D
	var slide := Vector3.RIGHT * 2.5
	var opened := false
	var _t := -1.0
	var _rest := Vector3.ZERO

	func setup(leaf: Node3D, size: Vector3, offset := Vector3.ZERO) -> void:
		body = AnimatableBody3D.new()
		body.collision_layer = 1
		body.sync_to_physics = true
		body.set_meta("surface", "metal")
		add_child(body)
		body.position = offset
		if leaf:
			body.add_child(leaf)
		var cs := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = size
		cs.shape = bs
		cs.position = Vector3(0, size.y * 0.5, 0)
		body.add_child(cs)
		_rest = offset   # with sync_to_physics the position reads back stale until the next tick

	func open_now(instant := false) -> void:
		if opened:
			return
		opened = true
		if instant:
			body.position = _rest + slide
			return
		_t = 0.0
		Sfx.play_3d("blast_door_open" if ResourceLoader.exists("res://assets/audio/blast_door_open.wav") else "door_open", global_position + Vector3.UP * 1.5, 4.0, 0.0, 12.0)
		Fx.smoke(global_position + Vector3.UP * 0.4)
		Fx.smoke(global_position + Vector3(0.8, 0.4, 0))

	func _physics_process(dt: float) -> void:
		if _t < 0.0:
			return
		_t += dt
		var k := clampf((_t - 0.6) / 2.6, 0.0, 1.0)
		k = k * k * (3.0 - 2.0 * k)
		body.position = _rest + slide * k
		if _t > 3.4:
			_t = -1.0

	func bot_open(_bot: Node) -> void:
		pass   # robots cannot open a blast door

	func is_open() -> bool:
		return opened


## Steam purge valve: floods a room with steam (robots' sight collapses).
class SteamValve extends HoldStation:
	var room := ""
	var volume: FogVolume
	var center := Vector3.ZERO
	var cooldown := 0.0

	func get_prompt(p: Node) -> String:
		if cooldown > 0.0:
			return "STEAM PURGE RECHARGING"
		return super.get_prompt(p)

	func _process(dt: float) -> void:
		cooldown = maxf(0.0, cooldown - dt)
		if cooldown <= 0.0 and _done:
			_done = false
		var obscured: bool = Game.room_obscured(room)
		if volume:
			var target := 0.55 if obscured else 0.0
			var m: FogMaterial = volume.material
			m.density = move_toward(m.density, target, dt * (0.6 if obscured else 0.08))
			volume.visible = m.density > 0.01
		if obscured and randf() < dt * 6.0:
			Fx.smoke(center + Vector3(randf_range(-7, 7), randf_range(0.3, 3.0), randf_range(-9, 9)))
