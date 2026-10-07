type CheckboxProps = {
  label: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}

export function CheckboxField({ label, checked, disabled = false, onChange }: CheckboxProps) {
  return (
    <label className="check">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  )
}

type NumberProps = {
  label: string
  value: number | null
  min: number
  max?: number
  onChange: (value: number | null) => void
}

export function NumberField({ label, value, min, max, onChange }: NumberProps) {
  return (
    <label className="setting">
      <span className="setting-title">{label}</span>
      <input
        aria-label={label}
        className="adv-input"
        type="number"
        min={min}
        max={max}
        value={value ?? ''}
        onChange={(event) =>
          onChange(event.target.value === '' ? null : Number(event.target.value))
        }
      />
    </label>
  )
}

type SelectProps<Value extends string> = {
  label: string
  value: Value
  options: readonly Value[]
  onChange: (value: Value) => void
}

export function SelectField<Value extends string>({
  label,
  value,
  options,
  onChange,
}: SelectProps<Value>) {
  return (
    <label className="setting">
      <span className="setting-title">{label}</span>
      <select
        aria-label={label}
        className="fake-select"
        value={value}
        onChange={(event) => onChange(event.target.value as Value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  )
}
