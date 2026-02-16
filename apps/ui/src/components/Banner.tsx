interface BannerProps {
  message: string;
  visible: boolean;
}

export function Banner({ message, visible }: BannerProps) {
  if (!visible) return null;

  return (
    <div className="cash-banner">
      {message || "Cash is a position."}
    </div>
  );
}
