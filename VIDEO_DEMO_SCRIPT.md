# video demo script

Target ~8 min. Zoom screen-share + record-locally.

before recording:
- `kubectl get pods` shows 3 Running
- `curl http://wsuan-test.coe332.tacc.cloud/help` returns the routes JSON
- two terminals open: one SSH'd into the VM at `~/launch-analysis-api`, one local
- repo open in a browser tab: https://github.com/willsuan/launch-analysis-api
- mic is unmuted, no notifications popping in

## 1. intro (~45 s)

Hi, I'm Will Suan and this is Dilynn Derden. For our 332 final, we built
a distributed REST API for analyzing space launch data, focused on NASA's
Artemis program.

Data source is the Launch Library 2 API, a public dataset of about 7,800
historical and upcoming orbital launches. We loaded all of them into Redis,
serve them through FastAPI, and added a worker process that generates plots
in response to user-submitted analysis jobs. The whole stack runs on the
class Kubernetes cluster.

Show: GitHub repo home page, scroll through the directory listing slowly.

## 2. kubernetes resources (~90 s)

Switch to terminal 1 (the VM).

```
kubectl get pods
```

Three pods running. Redis stores the data, the API runs FastAPI on port
5000, the worker runs an infinite loop pulling jobs off a Redis queue.

```
kubectl get svc
```

ClusterIP services let pods inside the cluster talk to each other. The
API connects to Redis through `artemis-test-redis-service`. The NodePort
service exposes the API outside the cluster's internal network.

```
kubectl get ingress
```

The Ingress maps the public hostname `wsuan-test.coe332.tacc.cloud` to
the API service. That's the URL anyone on the internet can hit.

```
kubectl get pvc
```

PersistentVolumeClaim attached to Redis, holds RDB snapshots and the
append-only log so data survives pod restarts. That covers the backup
and restore requirement.

## 3. the data (~60 s)

Switch to terminal 2 (laptop).

```
curl -s http://wsuan-test.coe332.tacc.cloud/help | jq
```

`/help` lists every available route. 13 endpoints total: CRUD for the
raw data, REST-style collections for launches, missions, and agencies,
plus the job submission and result retrieval endpoints.

```
curl -s http://wsuan-test.coe332.tacc.cloud/launches | jq 'length'
```

7,851 launches loaded.

```
curl -s 'http://wsuan-test.coe332.tacc.cloud/launches?provider=SpaceX' | jq '.[0] | {name, net, status: .status.name, mission: .mission.name}'
```

A SpaceX Falcon 9 launch with name, scheduled time, status, mission. The
full record has dozens of fields.

## 4. filtering (~45 s)

```
curl -s 'http://wsuan-test.coe332.tacc.cloud/launches?provider=SpaceX' | jq 'length'
```

790 SpaceX launches.

```
curl -s 'http://wsuan-test.coe332.tacc.cloud/launches?start_date=2020-01-01&end_date=2025-12-31' | jq 'length'
```

About 1,500 launches in the 2020s, a sharp uptick from the historical
baseline. Filters can be combined freely.

```
curl -s 'http://wsuan-test.coe332.tacc.cloud/launches?status=Failure' | jq 'length'
```

556 documented failures across the dataset.

## 5. submit a job (~90 s)

Now the asynchronous part.

```
JOB=$(curl -s -X POST http://wsuan-test.coe332.tacc.cloud/jobs \
  -H 'Content-Type: application/json' \
  -d '{"plot_type":"frequency_by_provider"}' | jq -r .id)
echo "$JOB"
```

API returned a UUID immediately. Behind the scenes it created a job record
in Redis with status "queued" and pushed the UUID onto a Redis LIST acting
as a queue.

```
curl -s "http://wsuan-test.coe332.tacc.cloud/jobs/$JOB" | jq
```

Status went from "queued" to "in_progress" to "complete". The worker pod
was blocking on a BLPOP against the queue, woke up the moment our job
arrived, fetched the launch data, ran matplotlib, and stored the PNG bytes
back in Redis under that same UUID.

```
curl -s "http://wsuan-test.coe332.tacc.cloud/results/$JOB" -o ~/Desktop/demo.png && open ~/Desktop/demo.png
```

Top 15 launch providers by launch count. Soviet Space Program leads
historically, SpaceX has rocketed up the chart in recent years.

## 6. another analysis (~45 s)

```
JOB=$(curl -s -X POST http://wsuan-test.coe332.tacc.cloud/jobs \
  -H 'Content-Type: application/json' \
  -d '{"plot_type":"success_rate_over_time"}' | jq -r .id)
sleep 4
curl -s "http://wsuan-test.coe332.tacc.cloud/results/$JOB" -o ~/Desktop/success.png && open ~/Desktop/success.png
```

Each year is a stacked bar with successes in green and failures in red.
You can see the 1960s space race, the steady plateau through the late 20th
century, and the dramatic ramp from 2018 onward, mostly Starlink.

## 7. architecture (~45 s)

Switch to GitHub, open `diagram.png`.

User hits FastAPI over HTTP. FastAPI reads from and writes to Redis but
never generates plots itself. The worker pod blocks on a Redis queue and
runs matplotlib in headless mode whenever a job arrives. Four logical
Redis databases keep concerns separate: raw data, the queue, job metadata,
and result images. RDB snapshots and the append-only log persist on a PVC.

Same Docker image runs in compose locally and on Kubernetes in production.

## 8. wrap (~30 s)

Repo is at github.com/willsuan/launch-analysis-api. README, all the k8s
manifests for test and prod, Dockerfile, docker-compose, the test suite,
the diagram. 21 pytest cases cover every endpoint and every plot generator,
running against fakeredis so the suite has no external dependencies.

Thanks for watching.

## tips

- run through it once without recording first
- don't read; glance at the bullets and say it
- terminal at 16pt+ so it's readable
- under 10 min total per the rubric, ~8 is the target
- if you flub a section, pause for two seconds and redo just that block;
  zoom keeps rolling and you can edit out flubs

## submission email

```
To: jstubbs@tacc.utexas.edu, nfreeman@tacc.utexas.edu, charlie@tacc.utexas.edu
Subject: Final Project

Final project submission, Will Suan and Dilynn Derden:

  Repo:       https://github.com/willsuan/launch-analysis-api
  Public URL: http://wsuan-test.coe332.tacc.cloud/help
  Write-up:   attached PDF
  Video:      <zoom share link>

Thanks,
Will
```
