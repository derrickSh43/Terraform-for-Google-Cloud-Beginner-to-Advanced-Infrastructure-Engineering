# Lesson 23 Challenge — Governance details that bite later

```powershell
python course.py check 23 --challenge
```

| ID | Requirement |
|---|---|
| C23.1 | **Essential contacts.** `google_essential_contacts_contact` on the Meridian folder for `SECURITY` and `BILLING` (an `essential_contacts` map: category → email). Otherwise Google mails whoever created each project, who may have left. |
| C23.2 | **Data residency.** `gcp.resourceLocations` on the Meridian folder with `allowed_values = ["in:us-locations"]`. Check that lesson 22's NAM4 and `us` locations are still allowed. |
| C23.3 | **Log costs.** An `exclusions` block on the folder sink that keeps successful load balancer request logs (`resource.type="http_load_balancer" AND httpRequest.status<400`) out of the central bucket. |
| C23.4 | **Project ID limit.** IDs are at most 30 characters and the factory adds a 5-character suffix: reject names longer than 25. The lesson test runs inside `modules/project-factory` (`tests/challenge/modules/project-factory`). |

## Think about it

- The location policy blocks a new resource type that only exists in `global`. How do you allow it without weakening the policy for everything else?
- Excluded logs still exist in each project's `_Default` bucket for 30 days. When is that not enough?
- What else should the factory refuse? Write down three validations you'd add for a real company.
