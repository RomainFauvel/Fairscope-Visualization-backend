# Importing necessary libraries for data visualization, web application development, data manipulation, and threading
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, no_update, callback
import pandas as pd
import os
import paho.mqtt.client as mqtt

# Importing a custom utility module
import utils

# Definition of the WorldMap class
class WorldMap:
    def __init__(self, controller,app):
        # Initialization method with a controller parameter for external interactions
        self.controller = controller
        self.app = app

        # Setting up publication and server details
        self.publisher = "visualization/dataset"
       

        # Reading data from a JSON file
        data_path = os.path.join('..', 'data/export/')
        self.df = self.create_df(data_path)

        # Hidding the mode bar
        self.config = {'displayModeBar': False}

        # Setting up the Dash web application
        self.world_map()


    def create_df(self, path):
        # Method to create a DataFrame from TSV files in a directory
        columns = ['filename', 'Objects/ml', 'date', 'lat', 'lon']
        df = pd.DataFrame(columns=columns)
        tsvs = utils.find_tsv_files(path)



        # Helper function to extract a value or return a default if not available
        def get_value(df, column, default=1):
            if column in df.columns and not df[column].empty:
                try:
                    value = float(df[column].iloc[0])
                    return value if value else default
                except (ValueError, TypeError):
                    return default
            return default

        data_list = []

        for tsv in tsvs:
            df_temp, nb_objects, metadatas = utils.load_dataframe(tsv)
            
            acq_imaged_volume = get_value(df_temp, "acq_imaged_volume")
            sample_dilution_factor = get_value(df_temp, "sample_dilution_factor")
            sample_concentrated_sample_volume = get_value(df_temp, "sample_concentrated_sample_volume")
            sample_total_volume = get_value(df_temp, "sample_total_volume")

            filename=os.path.basename(tsv)
            filename=filename.split("zip:")[-1]

            data = {
                "filename": filename,
                "Objects/ml": (nb_objects / acq_imaged_volume) * sample_dilution_factor * (sample_concentrated_sample_volume / (sample_total_volume * 1000)),
                "date": df_temp["acq_local_datetime"].iloc[0] if "acq_local_datetime" in df_temp.columns and not df_temp["acq_local_datetime"].empty else None,
                "lat": df_temp["object_lat"].iloc[0] if "object_lat" in df_temp.columns and not df_temp["object_lat"].empty else None,
                "lon": df_temp["object_lon"].iloc[0] if "object_lon" in df_temp.columns and not df_temp["object_lon"].empty else None
            }
            data_list.append(data)
        
        # delete duplicates
        data_list = [i for n, i in enumerate(data_list) if i not in data_list[n + 1:]]

        df = pd.concat([df, pd.DataFrame(data_list)], ignore_index=True)

        
                

        # Transform the 'date' column to datetime format
        df['date'] = pd.to_datetime(df['date'])
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')

        return df

    def create_world_map_fig(self):
        # Method to create a Plotly figure for a world map visualization
        fig = px.scatter_geo(
            self.df,
            lat="lat",
            lon="lon",
            color="Objects/ml",  # Column for marker color
            projection="natural earth",
            color_continuous_scale=px.colors.sequential.Bluered,  # Using a predefined color scale
            hover_data={"filename": True,"date":True,"Objects/ml": ":.2f","lat": ":.0f","lon": ":.0f"}, # Displaying additional data on hover
            custom_data="filename"
        )

        # Updating figure layout and trace properties
        fig.update_layout(
            autosize=True,
            margin=dict(l=0, r=0, t=0, b=0),
            height=None,
            width=None
        )

        # Updating marker properties
        size = [10] * len(self.df)
        opacity = [0.5] * len(self.df)
        fig.update_traces(marker=dict(size=size, opacity=opacity))

        # Adjusting color axis properties for the color bar
        fig.update_coloraxes(colorbar=dict(
            thickness=10,  # Adjusting color bar thickness
            len=0.9,  # Adjusting color bar length
            yanchor="middle",  # Vertically anchoring at the middle
            y=0.5,  # Vertically positioning at the middle
        ))

        return fig

    def world_map(self):
        # Method to setup and run the Dash web application
        self.fig = self.create_world_map_fig()


        # Defining the layout of the web application
        self.app.layout = html.Div([
            dcc.Graph(id='world-map', figure=self.fig, clear_on_unhover=True,config=self.config,
                      style={'position': 'relative', 'flex':1})
        ],
            style={'position': 'relative', 
                   'display': 'flex',
                   'margin': 0,
                   'padding': 0,
                   'overflow': 'hidden',
                   'align-items': 'center',
                   'justify-content': 'center'
                   }
        )

        @self.app.callback(
            Output('world-map', 'figure'),
            Input('world-map', 'clickData')
        )
        def select_point(clickData):
            # Callback function to handle click events on the world map
            if clickData is None:
                return no_update

            # Highlighting the selected point on the world map
            selected_point = clickData['points'][0]

            # Updating the figure with the highlighted point
            opacity = [1 if i == selected_point['pointNumber'] else 0.5 for i in range(len(self.df))]
            self.fig.update_traces(marker=dict(opacity=opacity))

            # Send the selected point to MQTT visualization/dataset
            
            dataset_name = selected_point['customdata'][0]
            self.controller.publish(self.publisher, dataset_name)
                

            return self.fig

       
# Example usage section
if __name__ == "__main__":
    app = Dash(__name__)  # Creating an instance of Dash for the web application
    world_map = WorldMap(None,app)  # Creating an instance of WorldMap without a controller for demonstration
    app.run(debug=True, use_reloader=False)  # Running the web application