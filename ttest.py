from app.schemas import CEFRLevel

group_name = "A1"
group_name = [level.value for level in CEFRLevel if level.name == group_name][
    0
]
# print(group_name)

ordered_levels = [level.name for level in CEFRLevel]
print(ordered_levels)
print(type(ordered_levels[1]))
