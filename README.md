<!--[![Join on Reddit](https://img.shields.io/reddit/subreddit-subscribers/Anagnorisis?style=social)](https://www.reddit.com/r/Anagnorisis)-->

# Anagnorisis
[![Anagnorisis Health](https://oss-health-monitor.vercel.app/api/badge/volotat/Anagnorisis?v=2)](https://github.com/volotat/OSS-Health-Monitor)

Anagnorisis - is a local recommendation system that allows you to fine-tune models on your data to predict your data preferences. You can feed it as much of your personal data as you like and not be afraid of it leaking as all of it is stored and processed locally on your own computer. All you need  to run it is 8GB VRAM GPU or 16GB of RAM in CPU-only mode. 


The project uses [Flask](https://flask.palletsprojects.com/) libraries for backend and [Bulma](https://bulma.io/) as frontend CSS framework. For all ML-related stuff [Transformers](https://github.com/huggingface/transformers) and [PyTorch](https://pytorch.org/) are used. This is the main technological stack, however there are more libraries used for specific purposes.


To find more about the project and ideas behind it you can read these articles:  
[Anagnorisis. Part 1: A Vision for Better Information Management.](https://volotat.github.io/p/anagnorisis-part-1-a-vision-for-better-information-management/)  
[Anagnorisis. Part 2: The Music Recommendation Algorithm.](https://volotat.github.io/p/anagnorisis-part-2-the-music-recommendation-algorithm/)  
[Anagnorisis. Part 3: Why Should You Go Local?](https://volotat.github.io/p/anagnorisis-part-3-why-should-you-go-local/)  
[Anagnorisis. Part 4: File Sharing is All We Need.](https://volotat.github.io/p/anagnorisis-part-4-file-sharing-is-all-we-need/)

And watch these videos:  
[Anagnorisis: Search Your Data Effectively (v0.3.1)](https://www.youtube.com/watch?v=X1Go7yYgFlY) - How to effectively search your data across all modules.  
[Anagnorisis: Music Module Preview (v0.1.6)](https://www.youtube.com/watch?v=vux7mDaRCeY) - Presentation of 'Music' module usage. To see how the algorithm works in details, please read this wiki page: [Music](wiki/music.md)  
[Anagnorisis: Images module preview (v0.1.0)](https://www.youtube.com/watch?v=S70Lp0oL7aQ) - Presentation of 'Images' module usage. Or you can read the guide at the [Images wiki](wiki/images.md) page.  

## General
Here is the main pipeline of working with the project:  
1. You rate some data such as text, audio, images, video or anything else on the scale from 0 to 10 and all of this is stored in the project database.  
2. When you acquire some amount of such rated data points you go to the 'Train' page and start the fine-tuning of the model so it could rate the data AS IF it was rated by you.  
3. New model is used to sort new data by rates from the model and if you do not agree with the scores the model gave, you simply change it.  

You repeat these steps again and again, getting each time model that better and better aligns to your preferences.  

The big vision of this project is to provide a platform that creates a local, private model of your interests. That likes what you like and sees importance where you would see it. Then you can use this model to search and filter local and global information on your behalf in a way you would do it yourself but in a much faster and efficient way. Making this platform (in the future) a go to place to see news, recommendations and insights, and so on, tailored specifically for you. As the internet gets populated with bots and AI slop, a platform like this might create a necessary filter to be able to navigate in this chaotic information space efficiently.
## How search works

There are three search modes, that are used for different kind of search:

- **Filename-based search** is a typical fuzzy-matching search that compares your query with file names, both local and remote.
- **Content-based search** embeds the *file itself* with the embedding model and compares embedding of your query with the embeddings of files to find the best matches. Only local files are supported for that kind of search to avoid unsolicited downloads from the remote servers. 
- **Metadata-based search** embeds a *text description* of the file: its name and path, an automatic description from the descriptor model (only local), zero-shot tags (only local), internal metadata (EXIF, ID3 tags, etc.) (also only local), and the contents of its `{filename}.meta` sidecar (local and remote in case such file exists). This special file allows you to describe local files subjectively (i.e. "photo of MY grandpa") and have a completely personalized search because of it. For the remote files it acts as a lightweight proxy for an actual file content, allowing for semantic search and recommendation in distributed networks.

Two rules the project holds to:

- **Searching never uses the GPU.** Your query is embedded on the CPU, in-process. The GPU is used only by background tasks you can see and pause on the Task Manager page.
- **Remote files are never downloaded automatically.** Background indexing reads only local files.

Because searching reads from the index rather than building it, files that have not been indexed yet simply do not appear in results. The status bar reports how many are still pending.

## Running from Docker
The preferred way to run the project is from Docker. This should be much more stable than running it from the local environment, especially on Windows.

1. Make sure that you have Docker installed. In case it is not go to [Docker installation page](https://www.docker.com/get-started/) and install it. 
2. Clone this repository:
    ```bash
    git clone https://github.com/volotat/Anagnorisis.git
    cd Anagnorisis
    ```
3. Create your configuration file from the provided example:
    ```bash
    cp docker-compose.override.example.yaml docker-compose.override.yaml
    ```
4. Open `docker-compose.override.yaml` in any text editor and replace the placeholder paths with your actual folder paths. For example:
    ```yaml
    volumes:
      # Project config (database, trained models, cache)
      - /home/user/Anagnorisis-config:/mnt/project_config

      # Your image folders:
      - /home/user/Photos:/mnt/media/images/Photos

      # Your music folders:
      - /home/user/Music:/mnt/media/music/Music

      # Your text folders:
      - /home/user/Documents:/mnt/media/text/Documents

      # Your video folders:
      - /home/user/Videos:/mnt/media/videos/Videos
    ```
    Each line follows the format: `/path/on/your/computer:/mnt/media/TYPE/LABEL`  
    - Use **absolute paths** (starting with `/` on Linux/Mac, or `C:/` on Windows).  
    - `TYPE` is one of: `images`, `music`, `text`, `videos`.  
    - `LABEL` is any name you choose — it will appear as a folder name in the app.  
    
    **Only the folders you list here will be accessible from inside the container.** No other folders on your system can be reached.

5. Launch the application:
    ```bash
    docker compose up -d
    ```
    Note: if you are using Docker Desktop you have to explicitly provide access to your data folders in the Docker settings. To do so, go to Docker Desktop settings, then to Resources -> File Sharing and add the paths to your data folders.
6. Access the application at http://localhost:5001 (or whichever port you configured) in your web browser.
7. To stop the application:
    ```bash
    docker compose down
    ```

Your configuration in `docker-compose.override.yaml` is preserved between restarts. You only need to edit it once.

### Multiple Media Folders Per Module

You can mount **as many folders as you need** for each media type. Each folder will appear as a separate top-level folder in the app's file browser. For example, to add multiple image sources:

```yaml
volumes:
  - /home/user/Anagnorisis-config:/mnt/project_config
  
  # Multiple image sources:
  - /home/user/Photos:/mnt/media/images/Photos
  - /media/external/DCIM:/mnt/media/images/Phone
  - /home/user/Screenshots:/mnt/media/images/Screenshots

  # Multiple music sources:
  - /home/user/Music/MyCollection:/mnt/media/music/MyCollection
  - /media/external/Vinyl:/mnt/media/music/Vinyl

  # ...
```

Inside the app, the Images module would show three top-level folders: `Photos`, `Phone`, and `Screenshots`, each containing the files from the corresponding folder on your computer. All search, sorting, and recommendation features work across all folders seamlessly.

### Running Multiple Instances

You can run several Anagnorisis instances simultaneously (e.g. for different family members) using separate configuration files. See the `instances/` folder for examples.

1. Copy an example and customize it:
    ```bash
    cp instances/example-personal.yaml instances/personal.yaml
    ```
2. Edit `instances/personal.yaml` with your paths, a unique port, and a unique container name.
3. Start and stop with the `-f` flag:
    ```bash
    docker compose -f docker-compose.yaml -f instances/personal.yaml up -d
    docker compose -f docker-compose.yaml -f instances/personal.yaml down
    ```

Each instance needs a **unique project name** (the `name` key at the top of the file), a **unique container name**, a **unique port**, and its **own project config folder** (for separate databases and trained models). You can run as many instances as your hardware supports.

## Initialization

To avoid issues with corrupted models being downloaded, **be patient while the application is initializing for the first time**. All models are quite large and might take some time to download depending on your internet connection speed. You can check the progress in the `logs/{CONTAINER_NAME}_log.txt` file that will appear in the project's root folder. The project UI will also show the initialization status, but  for now without download progress percentages. 

If for some reason the initialization process is interrupted (for example you stopped the container while models were being downloaded), upon the next start the application will check for corrupted models and try to re-download them automatically. If this does not help, please delete the `models` folder inside the project's root folder and start the application again. This will force the application to download all models from scratch. 

## Troubleshooting

In case you encounter an error like this:
```
ERROR: for {your container name} Cannot start service anagnorisis: error while creating mount source path '/path/to/config': chown /path/to/config: operation not permitted
```

You have to create the folder specified as your project config mount target (the path before `:/mnt/project_config` in your `docker-compose.override.yaml`) manually on your host machine. Docker sometimes cannot create such folders by itself due to permission issues.

## Additional notes for installation
The Docker image (Python dependencies, PyTorch with CUDA runtime, system libraries) takes approximately 8 GB of disk space after building. On first startup the application downloads the required ML models that would take roughly 20 GB, most of it the descriptor model. If you use the project heavily with active use of external modules, their caches can grow to several additional gigabytes. As a rough total estimate, budget around 40 GB of free disk space before starting.

For best user experience I would recommend running the project with relatively modern Nvidia GPU with at least 8Gb of VRAM and 32Gb of RAM. At least this is the configuration I am using myself. However, the project should be able to run on lower configurations, but performance might be poor especially without CUDA-friendly GPU. Note that CPU-only mode might be significantly slower.

After initializing the project, you will find new `database` folder inside of the project config folder you specified. In this folder project's database, migrations, models and configuration file will be stored. After running the project for the first time, the `database/project.db` file will be created. That DB will store your preferences, that will be used later to fine-tune evaluation models. Try to make backups of this file from time to time, as it contains all of your preferences, and some additional data, such as playback history.

If you have a lot of data in your data folder, for the first time hash cache and embedding cache will be gathered. Please be patient, as it may take a while. The percentage of the progress will be shown in the status bar.

The project requires GPU to run properly. When running the project inside the Docker container, make sure that `NVIDIA Container Toolkit` is installed for Linux and `WSL2` for Windows.


## Modules

The application is built around a module system. Each module is a self-contained folder inside `modules/` that adds support for a new data type or functionality. Modules are **auto-discovered at startup** — dropping a module folder in and restarting is all that is needed to activate it.

Built-in modules: **Images**, **Music**, **Text**, **Videos**, **Train** (evaluator training UI).

### Installing an external module

External modules can be installed by cloning their repository directly into the `modules/` folder:

```bash
cd modules
git clone <module-repo-url>
```

Then rebuild and restart the container:

```bash
docker compose up -d --build
```

### Available external modules

| Module | Description | Status |
|--------|-------------|--------|
| [WebSearch](https://github.com/volotat/WebSearch) | Crawls and indexes websites, enabling semantic search and preference-based ranking over web content. | experimental |
| [YouTube](https://github.com/volotat/YouTube) | Treats YouTube as CDN leaving search and recommendations to Anagnorisis local algorithms. | experimental |

### Building your own module

See [`modules/_module_template/`](modules/_module_template/) for a fully documented reference implementation.


## Security notes
The project is meant to be run on the localhost only for now. The default configuration ip address is set to `127.0.0.1` inside `docker-compose.override.yaml` file. This means that the application will only be accessible from the machine it is running on. If you want to access it from other devices on your local network, you can change the port binding in your `docker-compose.override.yaml` to `0.0.0.0:5001:5001`. You can even tunnel it to the internet using services like [ngrok](https://ngrok.com/) or [cloudflare tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/). However, I would strongly recommend against exposing the service to the internet (unless you are 100% know what you are doing) as there is no proper security work has been done yet. 



## Models
The project runs two models:

[jinaai/jina-embeddings-v5-omni-small](https://huggingface.co/jinaai/jina-embeddings-v5-omni-small) — **the embedding model**. One model for every kind of content: text, images, audio and video all land in a single shared vector space. This replaced the three separate models the project used before (CLAP for audio, SigLIP for images, Qwen3 for text), each of which had its own incompatible space.

[Dystrio/MiniCPM-o-4_5-Sculpt-Throughput](https://huggingface.co/dystrio/MiniCPM-o-4_5-Sculpt-Throughput) — **the descriptor model**, which writes a natural-language description of a file. An optimized version of [MiniCPM-o-4_5](https://huggingface.co/openbmb/MiniCPM-o-4_5).

All models are downloaded automatically when the project is started for the first time. This might take some time depending on the internet connection. You can see the progress inside `logs/anagnorisis-app_log.txt` file that will appear in the project's root folder if you run the project from the Docker container.

**Huge thanks to [Dystrio](https://huggingface.co/dystrio) for optimizing the MiniCPM-o-4_5 model specifically for the Anagnorisis project, making it more then 2 times faster at token generation speed and providing even bigger context window with minimal loss in model's accuracy.**


## Wiki
The project has its own wiki that is integrated into the project itself, you might access it by running the project, or simply reading it as markdown files.

Here is some pages that might be interesting for you:  
[Change history](wiki/change_history.md)  
[Philosophy](wiki/philosophy.md)  
[Music](wiki/music.md)  
[Images](wiki/images.md)  
[Roadmap](wiki/roadmap.md)

---------------	
In memory of [Josh Greenberg](https://variety.com/2015/digital/news/grooveshark-josh-greenberg-dead-1201544107/) - one of the creators of Grooveshark. Long gone music service that had the best music recommendation system I've ever seen. 
