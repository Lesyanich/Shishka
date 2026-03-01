import matplotlib.pyplot as plt
import matplotlib.patches as patches

width_m  = 4.0   # горизонталь
height_m = 8.0   # вертикаль
margin   = 1.6

fig = plt.figure(figsize=(8.27, 11.69))
ax = fig.add_subplot(111)
ax.set_aspect('equal')
ax.axis('off')
ax.set_xlim(-margin, width_m + margin)
ax.set_ylim(-margin, height_m + margin)

# Контур помещения
rect = patches.Rectangle((0, 0), width_m, height_m,
                         linewidth=6, edgecolor='black', facecolor='none')
ax.add_patch(rect)

# Сетка каждые 50 см
for x in [0.5, 1.5, 2.5, 3.5]:
    ax.axvline(x, color='gray', lw=0.8, linestyle='--', alpha=0.6)
for y in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5]:
    ax.axhline(y, color='gray', lw=0.8, linestyle='--', alpha=0.6)

# === Вертикальные стороны (8 м) — подписи ГОРИЗОНТАЛЬНЫЕ подписи снаружи ===
for i in range(81):
    pos = round(i * 0.1, 1)
    if pos > height_m: continue

    if pos % 1.0 == 0 and pos > 0:
        tick_len = 0.40
        fs = 18
        weight = 'bold'
        offset = 0.20
    elif i % 2 == 0 and pos > 0:
        tick_len = 0.25
        fs = 11
        weight = 'normal'
        offset = 0.12
    else:
        tick_len = 0.15
        fs = None
        offset = 0

    # Риски наружу
    ax.plot([0, -tick_len], [pos, pos], color='black', lw=3.5)
    ax.plot([width_m, width_m + tick_len], [pos, pos], color='black', lw=3.5)

    if fs:
        label = str(int(pos)) if pos % 1 == 0 else f"{pos:.1f}"
        # Левая сторона — подпись слева и горизонтально
        ax.text(-tick_len - offset, pos, label,
                ha='right', va='center', fontsize=fs, fontweight=weight)
        # Правая сторона — подпись справа и горизонтально
        ax.text(width_m + tick_len + offset, pos, label,
                ha='left', va='center', fontsize=fs, fontweight=weight)

# === Горизонтальные стороны (4 м) — подписи ВЕРТИКАЛЬНЫЕ (90°) ===
for i in range(41):
    pos = round(i * 0.1, 1)
    if pos > width_m: continue

    if pos % 1.0 == 0 and pos > 0:
        tick_len = 0.40
        fs = 18
        weight = 'bold'
        offset = 0.20
    elif i % 2 == 0 and pos > 0:
        tick_len = 0.25
        fs = 11
        weight = 'normal'
        offset = 0.12
    else:
        tick_len = 0.15
        fs = None
        offset = 0

    # Риски наружу
    ax.plot([pos, pos], [0, -tick_len], color='black', lw=3.5)
    ax.plot([pos, pos], [height_m, height_m + tick_len], color='black', lw=3.5)

    if fs:
        label = str(int(pos)) if pos % 1 == 0 else f"{pos:.1f}"
        # Снизу
        ax.text(pos, -tick_len - offset, label,
                ha='center', va='top', fontsize=fs, fontweight=weight,
                rotation=90)
        # Сверху
        ax.text(pos, height_m + tick_len + offset, label,
                ha='center', va='bottom', fontsize=fs, fontweight=weight,
                rotation=90)

# Общие размеры
ax.text(width_m/2, -2.1, '4.0 м', fontsize=26, fontweight='bold', ha='center')
ax.text(width_m/2, height_m + 2.1, '4.0 м', fontsize=26, fontweight='bold', ha='center')
ax.text(-2.6, height_m/2, '8.0 м', fontsize=26, fontweight='bold', va='center', rotation=90)
ax.text(width_m + 2.6, height_m/2, '8.0 м', fontsize=26, fontweight='bold', va='center', rotation=90)

plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
plt.savefig('L2_TOPS_4x8_CLEAN_FINAL.pdf', dpi=600, bbox_inches='tight', pad_inches=0.7)
plt.savefig('L2_TOPS_4x8_CLEAN_FINAL.png', dpi=600, bbox_inches='tight', pad_inches=0.7)
plt.show()