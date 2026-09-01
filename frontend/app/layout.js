import "./globals.css";

export const metadata = {
  title: "Resume and Apply",
  description: "Resume tailoring using AI and Job Tracking",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
