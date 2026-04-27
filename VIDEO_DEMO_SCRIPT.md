# Video Demo Script — Artemis II Launch Data Analysis API

**Target length:** ~8 minutes
**Recording tool:** Zoom screen-share + record-locally (or QuickTime)
**Pre-flight checklist:**

- [ ] Cluster is up: `kubectl get pods` shows 3 Running
- [ ] Public URL responds: `curl http://wsuan-test.coe332.tacc.cloud/help`
- [ ] Browser windows open and ready:
  - GitHub repo: <https://github.com/willsuan/launch-analysis-api>
  - Public help endpoint: <http://wsuan-test.coe332.tacc.cloud/help>
- [ ] Two terminals open and arranged on screen:
  - Terminal 1: SSH'd into the VM, in `~/launch-analysis-api`
  - Terminal 2: local laptop terminal
- [ ] `jq` filter ready (you'll pipe most curls through it)
- [ ] Microphone working, no notifications popping up

---

## Section 1 — Introduction (≈45 sec)

> Hi, I'm Will Suan, and this is Dilynn Derden. For our COE 332 final project, we built a distributed REST API system for analyzing space launch data, with a focus on NASA's Artemis program.
>
> The system uses the Launch Library 2 API as its data source — that's a public dataset of about 7,800 historical and upcoming orbital launches. We loaded all of them into Redis, exposed them through a FastAPI server, and added a worker process that generates plots in response to user-submitted analysis jobs. The whole stack runs on the class Kubernetes cluster.

**Show on screen:** the GitHub repo home page, scrolling slowly through the directory listing so the audience can see the structure.

---

## Section 2 — Kubernetes resources (≈90 sec)

**Switch to Terminal 1 (the VM).**

> Let me start by showing the deployed resources on the cluster.

```bash
kubectl get pods
```

> We have three pods running. The Redis pod stores all our data. The API pod runs FastAPI on port 5000. The worker pod runs an infinite loop that pulls jobs off a Redis queue.

```bash
kubectl get svc
```

> Here are our services. ClusterIP services let pods inside the cluster talk to each other — for example, the API pod connects to Redis through `artemis-test-redis-service`. The NodePort service exposes the API outside the cluster's internal network.

```bash
kubectl get ingress
```

> And the Ingress object maps the public hostname `wsuan-test.coe332.tacc.cloud` to the API service. That's the URL anyone on the internet can hit to talk to our deployment.

```bash
kubectl get pvc
```

> Finally, we have a PersistentVolumeClaim attached to the Redis pod, which holds RDB snapshots and an append-only log so the data survives pod restarts. That covers the backup and restore requirement from the assignment.

---

## Section 3 — The data (≈60 sec)

> Let me hit the public URL to show what we're working with.

**Switch to Terminal 2 (laptop).**

```bash
curl -s http://wsuan-test.coe332.tacc.cloud/help | jq
```

> The `/help` endpoint lists every available route. Thirteen endpoints in total — CRUD for the raw data, REST-style collections for launches, missions, and agencies, and the job submission and result retrieval endpoints.

```bash
curl -s http://wsuan-test.coe332.tacc.cloud/launches | jq 'length'
```

> 7,851 launches loaded. Each one is a dictionary with deeply nested fields: rocket configuration, mission, agency, pad, status, timestamps. Let me grab one:

```bash
curl -s 'http://wsuan-test.coe332.tacc.cloud/launches?provider=SpaceX' | jq '.[0] | {name, net, status: .status.name, mission: .mission.name}'
```

> That's a SpaceX Falcon 9 launch with the name, scheduled time, status, and mission. The full record has dozens of additional fields. The Artemis II mission, which inspired the project, looks like this:

```bash
curl -s 'http://wsuan-test.coe332.tacc.cloud/launches?provider=National%20Aeronautics' | jq '.[] | select(.name | contains("Artemis"))' | head -30
```

---

## Section 4 — Filtering (≈45 sec)

> The launches collection supports query parameters. Let me show a couple.

```bash
# Filter by provider
curl -s 'http://wsuan-test.coe332.tacc.cloud/launches?provider=SpaceX' | jq 'length'
# 790
```

> 790 SpaceX launches across history.

```bash
# Filter by date range
curl -s 'http://wsuan-test.coe332.tacc.cloud/launches?start_date=2020-01-01&end_date=2025-12-31' | jq 'length'
```

> Roughly 1,500 launches in the 2020s — a sharp uptick from the historical baseline, which is exactly what one of our analyses shows.

```bash
# Filter by status
curl -s 'http://wsuan-test.coe332.tacc.cloud/launches?status=Failure' | jq 'length'
# 556
```

> 556 documented launch failures across the dataset. These filters can be combined freely.

---

## Section 5 — Submitting an analysis job (≈90 sec)

> Now the asynchronous part. The job submission flow is what differentiates this from a typical CRUD API.

```bash
JOB=$(curl -s -X POST http://wsuan-test.coe332.tacc.cloud/jobs \
  -H 'Content-Type: application/json' \
  -d '{"plot_type":"frequency_by_provider"}' | jq -r .id)
echo "$JOB"
```

> The API returned a UUID immediately. Behind the scenes it created a job record in Redis with status "queued" and pushed the UUID onto a Redis LIST acting as a job queue. Let me look at the job:

```bash
curl -s "http://wsuan-test.coe332.tacc.cloud/jobs/$JOB" | jq
```

> Status went from "queued" to "in_progress" to "complete" — the worker pod has been blocking on a `BLPOP` against the queue, woke up the moment our job arrived, fetched the launch data from Redis, ran matplotlib to generate the plot, and stored the resulting PNG bytes back in Redis under that same UUID.

> Now I'll pull the image:

```bash
curl -s "http://wsuan-test.coe332.tacc.cloud/results/$JOB" -o ~/Desktop/demo.png && open ~/Desktop/demo.png
```

> And there it is — the top 15 launch providers by launch count. The Soviet Space Program leads historically, and SpaceX has rocketed up the chart in recent years.

---

## Section 6 — A second analysis (≈45 sec)

> Let me run one more, this time the success-rate-over-time plot, which is the most data-rich of the three:

```bash
JOB=$(curl -s -X POST http://wsuan-test.coe332.tacc.cloud/jobs \
  -H 'Content-Type: application/json' \
  -d '{"plot_type":"success_rate_over_time"}' | jq -r .id)
sleep 4
curl -s "http://wsuan-test.coe332.tacc.cloud/results/$JOB" -o ~/Desktop/success.png && open ~/Desktop/success.png
```

> Each year is a stacked bar with successes in green and failures in red. You can see the 1960s space race, the steady plateau through the late 20th century, and then the dramatic ramp from about 2018 onward, driven mostly by SpaceX Starlink missions.

---

## Section 7 — Architecture recap (≈45 sec)

**Switch to the GitHub repo browser tab; navigate to `diagram.png`.**

> Here's the architecture in one picture. The user hits FastAPI over HTTP. FastAPI reads from and writes to Redis but never generates plots itself. The worker pod blocks on a Redis queue and runs matplotlib in headless mode whenever a job arrives. We use four logical Redis databases to keep concerns separate: raw data, the queue, job metadata, and result images. RDB snapshots and the append-only log persist on a PersistentVolumeClaim.

> The whole thing runs locally with Docker Compose during development and on Kubernetes in production, with the same Docker image in both environments.

---

## Section 8 — Wrap-up (≈30 sec)

> The repository at github.com/willsuan/launch-analysis-api has the README, the Kubernetes manifests for both test and production, the Dockerfile, the docker-compose file, the test suite, and the architecture diagram. Twenty-one pytest cases cover every endpoint and every plot generator, and they run against a fakeredis instance so the test suite has no external dependencies.

> Thanks for watching.

---

## Recording tips

- **Practice run-through first.** Do the whole script once without recording to get a feel for the timing. The curls take a few seconds each — pause naturally during them.
- **Don't read.** Glance at the script bullet then say it in your own words. Slightly fluffed lines sound more authentic than perfect ones.
- **Show the terminal big.** Increase font size to ~16pt so it's readable in the recorded video.
- **One section per take if you fluff.** Zoom keeps the recording rolling; you can edit out flubs in QuickTime or Zoom's built-in editor.
- **Total target: 8 minutes** (the rubric says under 10). If a take runs to 9 minutes, that's fine.

## What to email

Once the recording is done:
1. Save Zoom recording locally (Zoom auto-uploads to cloud — get the share link).
2. Export `Final_Writeup.docx` to PDF (open in Word/Google Docs/Pages → File → Export as PDF).
3. Send one email to all three instructors with subject "Final Project". Body:
   > Hi Joe, Nathan, Charlie,
   >
   > Final project submission from Will Suan and Dilynn Derden:
   >
   > - Repo: https://github.com/willsuan/launch-analysis-api
   > - Public URL: http://wsuan-test.coe332.tacc.cloud/help
   > - Write-up PDF: attached
   > - Video demo: <Zoom share link>
   >
   > Thanks,
   > Will
