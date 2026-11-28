import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 24, children, ...rest }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const LeafIcon = (p: IconProps) => (
  <Svg {...p}><path d="M4 20c6 0 12-4 14-14-8 0-14 4-14 14z" /><path d="M4 20c3-5 6-8 10-10" /></Svg>
);
export const HomeIcon = (p: IconProps) => (
  <Svg {...p}><path d="M3 11l9-7 9 7v9H3z" /></Svg>
);
export const CameraIcon = (p: IconProps) => (
  <Svg {...p}><path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="4" /></Svg>
);
export const BellIcon = (p: IconProps) => (
  <Svg {...p}><path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z" /><path d="M10 20a2 2 0 0 0 4 0" /></Svg>
);
export const HelpIcon = (p: IconProps) => (
  <Svg {...p}><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 0 1 5 0c0 1.5-2.5 2-2.5 3.5" /><circle cx="12" cy="17" r="0.5" /></Svg>
);
export const BookIcon = (p: IconProps) => (
  <Svg {...p}><path d="M4 5h6a2 2 0 0 1 2 2v12a2 2 0 0 0-2-2H4zM20 5h-6a2 2 0 0 0-2 2v12a2 2 0 0 1 2-2h6z" /></Svg>
);
export const HeartIcon = (p: IconProps) => (
  <Svg {...p}><path d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.5-7 10-7 10z" /></Svg>
);
export const PhotoIcon = (p: IconProps) => (
  <Svg {...p}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M8 15l3-3 2 2 3-4 3 5" /></Svg>
);
export const MarkerIcon = (p: IconProps) => (
  <Svg {...p}><rect x="5" y="5" width="14" height="14" /><rect x="8" y="8" width="3" height="3" /><rect x="13" y="13" width="3" height="3" /></Svg>
);
export const ArrowLeftIcon = (p: IconProps) => (
  <Svg {...p}><path d="M15 5l-7 7 7 7" /></Svg>
);
export const ArrowRightIcon = (p: IconProps) => (
  <Svg {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Svg>
);
export const CheckIcon = (p: IconProps) => (
  <Svg {...p}><path d="M5 12l5 5 9-10" /></Svg>
);
export const GaugeIcon = (p: IconProps) => (
  <Svg {...p}><path d="M4 16a8 8 0 1 1 16 0" /><path d="M12 16l4-5" /><path d="M4 16h2M18 16h2M12 8V6" /></Svg>
);
export const CowIcon = (p: IconProps) => (
  <Svg {...p}><path d="M5 10c0-3 3-5 7-5s7 2 7 5v5H5z" /><path d="M7 15v4M17 15v4M4 6l2 3M20 6l-2 3" /></Svg>
);
export const PointsIcon = (p: IconProps) => (
  <Svg {...p}><circle cx="6" cy="7" r="2" /><circle cx="18" cy="9" r="2" /><circle cx="9" cy="17" r="2" /><path d="M8 8l8 1M7 9l2 6" /></Svg>
);
