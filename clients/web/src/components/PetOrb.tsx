export function PetOrb({ statusLabel }: { statusLabel: string }) {
  return (
    <div className="pet-orb breathing" role="img" aria-label={statusLabel}>
      <div className="pet-sphere">
        <div className="pet-face" aria-hidden="true">
          <div className="pet-eyes">
            <div className="pet-eye" />
            <div className="pet-eye" />
          </div>
          <div className="pet-mouth" />
        </div>
      </div>
    </div>
  );
}
