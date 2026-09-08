export function PetOrb({ statusLabel }: { statusLabel: string }) {
  return (
    <svg
      className="pet-orb paper-mascot"
      viewBox="0 0 360 270"
      role="img"
      aria-label={statusLabel}
      xmlns="http://www.w3.org/2000/svg"
    >
      <g
        stroke="#20232a"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M18 227 Q174 220 341 229" fill="none" />
        <g transform="rotate(-3 170 105)">
          <path
            d="m167 14 15 22 27-9 5 28 29 4-10 27 22 18-24 16 5 29-28 1-11 26-24-15-23 16-11-27-29-2 7-27-22-18 23-17-8-27 29-3 8-27 23 12Z"
            fill="#ffd34e"
          />
          <path
            d="M170 35 C259 37 263 169 174 175 C83 182 80 39 170 35Z"
            fill="#ffd34e"
          />
          <path
            d="M137 93v8m59-8v8m-52 27q23 20 44-2"
            fill="none"
            strokeWidth="5"
          />
        </g>
        <path
          d="m24 57 18-10 9 22-20 7Z"
          fill="#9275ed"
          transform="rotate(3 36 60)"
        />
        <path d="m290 41 12 17-20 3Z" fill="#ff917b" />
        <path d="M290 115c7-18 30-12 26 4-4 14-25 18-26-4Z" fill="#7ce0b5" />
        <g transform="rotate(2 240 197)">
          <path d="m213 224 24-61 31 62Z" fill="#9275ed" />
          <path
            d="m233 188 0 3m13-3 0 3m-19 34-4 15m31-15 6 15m-39-26-14-10m55 12 13-12"
            fill="none"
          />
        </g>
        <g transform="rotate(-2 103 206)">
          <path d="M83 220v-23c0-28 40-28 40 0v24Z" fill="#7ce0b5" />
          <path
            d="m96 196 0 3m13-3 0 3m-17 23-4 13m24-13 5 13m-35-24-10-13m53 16 9-12"
            fill="none"
          />
        </g>
        <path
          d="m52 142 8 0m-4-4 0 8m271 49 8 0m-4-4 0 8"
          fill="none"
          stroke="#6652b8"
        />
      </g>
    </svg>
  );
}
