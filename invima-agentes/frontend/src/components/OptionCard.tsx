type Props = {
  label: string;
  hint?: string;
  selected: boolean;
  variant?: 'default' | 'pay';
  onSelect: () => void;
};

export function OptionCard({ label, hint, selected, variant = 'default', onSelect }: Props) {
  const classes = ['option-card'];
  if (variant === 'pay') classes.push('option-card--pay');
  if (selected) classes.push('option-card--selected');

  return (
    <button type="button" className={classes.join(' ')} aria-pressed={selected} onClick={onSelect}>
      {variant === 'pay' ? (
        label
      ) : (
        <>
          <div className="option-card__label">{label}</div>
          {hint ? <div className="option-card__hint">{hint}</div> : null}
        </>
      )}
    </button>
  );
}
