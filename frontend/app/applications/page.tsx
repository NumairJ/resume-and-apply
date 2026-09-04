"use client";

import Link from "next/link";

import { useApplications } from "@/lib/queries";
import { ApplicationsTable } from "@/components/ApplicationsTable";
import { Button, Empty, Page, PageHeader } from "@/components/ui";

export default function ApplicationsPage() {
  const { data, isPending, isError, error } = useApplications();

  return (
    <Page>
      <PageHeader
        title="Applications"
        actions={
          <Link href="/apply">
            <Button variant="primary">Tailor a resume</Button>
          </Link>
        }
      >
        Everything you have tracked, and where each one stands.
      </PageHeader>

      {isPending && <Empty>Loading…</Empty>}
      {isError && <Empty>Could not load applications — {error.message}</Empty>}
      {data && <ApplicationsTable rows={data} />}
    </Page>
  );
}
